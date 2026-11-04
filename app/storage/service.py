import os
import shutil
import uuid
import json
from datetime import timedelta
from datetime import datetime, timezone
from pathlib import Path
from .database import Database
from .objects import ObjectStore

def now(): return datetime.now(timezone.utc).isoformat()
class StorageError(Exception):
    def __init__(self, code, message, status=500): self.code, self.message, self.status = code, message, status

class StorageService:
    def __init__(self, data_dir, multipart_retention_hours=24, max_object_size=5 * 1024 * 1024 * 1024, max_request_size=5 * 1024 * 1024 * 1024):
        self.root = Path(data_dir).resolve(); self.db = Database(self.root / "metadata" / "s3like.db"); self.files = ObjectStore(self.root); self.cleanup()
        self.multipart_retention_hours = multipart_retention_hours
        self.max_object_size = max_object_size
        self.max_request_size = max_request_size
    def cleanup(self):
        for p in self.files.tmp.glob("*"):
            if p.is_file(): self.files.remove(p)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=getattr(self, 'multipart_retention_hours', 24))
        with self.db.connect() as c:
            stale = c.execute("SELECT upload_id FROM multipart_uploads WHERE status='active' AND initiated < ?", (cutoff.isoformat(),)).fetchall()
            for row in stale:
                c.execute("DELETE FROM multipart_uploads WHERE upload_id=?", (row['upload_id'],))
        with self.db.connect() as c:
            active = {r['upload_id'] for r in c.execute("SELECT upload_id FROM multipart_uploads")}
        for p in self.files.multipart.glob('*'):
            if p.is_dir() and p.name not in active: shutil.rmtree(p, ignore_errors=True)
    def bucket(self, name):
        with self.db.connect() as c: return c.execute("SELECT * FROM buckets WHERE name=?", (name,)).fetchone()
    def list_buckets(self):
        with self.db.connect() as c: return c.execute("SELECT * FROM buckets ORDER BY name").fetchall()
    def require_bucket(self, name):
        if not self.bucket(name): raise StorageError("NoSuchBucket", "The specified bucket does not exist.", 404)
    def create_bucket(self, name):
        with self.db.transaction() as c:
            if c.execute("SELECT 1 FROM buckets WHERE name=?", (name,)).fetchone():
                raise StorageError("BucketAlreadyExists", "The bucket already exists.", 409)
            c.execute("INSERT INTO buckets VALUES (?,?)", (name, now()))

    def ensure_bucket(self, name):
        if not self.bucket(name): self.create_bucket(name)
    def delete_bucket(self, name):
        with self.db.transaction() as c:
            if not c.execute("SELECT 1 FROM buckets WHERE name=?", (name,)).fetchone(): raise StorageError("NoSuchBucket", "The specified bucket does not exist.", 404)
            if c.execute("SELECT 1 FROM objects WHERE bucket=? LIMIT 1", (name,)).fetchone(): raise StorageError("BucketNotEmpty", "The bucket is not empty.", 409)
            c.execute("DELETE FROM buckets WHERE name=?", (name,))
    def list_objects(self, bucket, prefix="", delimiter=None, start_after="", token=None, max_keys=1000):
        self.require_bucket(bucket)
        with self.db.connect() as c: rows = c.execute("SELECT * FROM objects WHERE bucket=? ORDER BY key", (bucket,)).fetchall()
        rows = [r for r in rows if r["key"].startswith(prefix) and r["key"] > start_after and (not token or r["key"] > token)]
        contents=[]; common=[]; seen=set()
        for r in rows:
            if delimiter:
                tail=r["key"][len(prefix):]; pos=tail.find(delimiter)
                if pos >= 0:
                    cp=prefix+tail[:pos+1]
                    if cp not in seen: common.append(cp); seen.add(cp)
                    continue
            contents.append(r)
        items=[("c",r) for r in contents]+[("p",p) for p in common]; items.sort(key=lambda x:x[1]["key"] if x[0]=="c" else x[1]); page=items[:max_keys]
        nxt=page[-1][1]["key"] if page and page[-1][0]=="c" else (page[-1][1] if page else None)
        return [r for t,r in page if t=="c"], [p for t,p in page if t=="p"], len(items)>max_keys, nxt
    def get_object(self, bucket, key):
        self.require_bucket(bucket)
        with self.db.connect() as c: row=c.execute("SELECT * FROM objects WHERE bucket=? AND key=?", (bucket,key)).fetchone()
        if not row: raise StorageError("NoSuchKey", "The specified key does not exist.", 404)
        path=self.files.final_path(row["storage_id"])
        if not path.exists(): raise StorageError("InternalError", "Object data is missing.")
        return row,path
    def put_object(self, bucket, key, source, content_type="application/octet-stream", metadata=None):
        self.require_bucket(bucket); size,etag=self.files.digest(source)
        if size > self.max_object_size:
            self.files.remove(source)
            raise StorageError("EntityTooLarge", "The object exceeds the configured maximum object size.", 413)
        sid=self.files.new_id(); final=None
        try:
            final=self.files.commit(source,sid)
            with self.db.transaction() as c:
                old=c.execute("SELECT storage_id FROM objects WHERE bucket=? AND key=?",(bucket,key)).fetchone()
                c.execute("INSERT OR REPLACE INTO objects VALUES (?,?,?,?,?,?,?,?)",(bucket,key,sid,size,etag,content_type,now(),json.dumps(metadata or {}, sort_keys=True)))
            if old: self.files.remove(self.files.final_path(old["storage_id"]))
            return self.get_object(bucket,key)[0]
        except Exception:
            if final: self.files.remove(final)
            raise
    def delete_object(self,bucket,key):
        self.require_bucket(bucket)
        with self.db.transaction() as c:
            old=c.execute("SELECT storage_id FROM objects WHERE bucket=? AND key=?",(bucket,key)).fetchone(); c.execute("DELETE FROM objects WHERE bucket=? AND key=?",(bucket,key))
        if old: self.files.remove(self.files.final_path(old["storage_id"]))
    def copy_object(self,bucket,key,src_bucket,src_key):
        row,path=self.get_object(src_bucket,src_key); tmp=self.files.new_temp()
        try:
            shutil.copyfile(path,tmp); return self.put_object(bucket,key,tmp,row["content_type"],json.loads(row["metadata"]))
        finally: self.files.remove(tmp)
    def initiate(self,bucket,key,content_type='application/octet-stream',metadata=None):
        self.require_bucket(bucket); uid=uuid.uuid4().hex; (self.files.multipart/uid).mkdir(parents=True,exist_ok=True)
        with self.db.transaction() as c: c.execute("INSERT INTO multipart_uploads(upload_id,bucket,object_key,initiated,status,content_type,metadata) VALUES (?,?,?,?,?,?,?)",(uid,bucket,key,now(),"active",content_type,json.dumps(metadata or {}, sort_keys=True)))
        return uid
    def upload_part(self,uid,number,source):
        with self.db.connect() as c: u=c.execute("SELECT * FROM multipart_uploads WHERE upload_id=? AND status='active'",(uid,)).fetchone()
        if not u:
            self.files.remove(source)
            raise StorageError("NoSuchUpload","The specified upload does not exist.",404)
        size,etag=self.files.digest(source)
        if size > self.max_object_size:
            self.files.remove(source)
            raise StorageError("EntityTooLarge", "The multipart part exceeds the configured maximum object size.", 413)
        target=self.files.multipart/uid/str(number); os.replace(source,target)
        with self.db.transaction() as c: c.execute("INSERT OR REPLACE INTO multipart_parts VALUES (?,?,?,?,?)",(uid,number,str(target),size,etag))
        return etag
    def parts(self,uid):
        with self.db.connect() as c:
            u=c.execute("SELECT * FROM multipart_uploads WHERE upload_id=? AND status='active'",(uid,)).fetchone(); p=c.execute("SELECT * FROM multipart_parts WHERE upload_id=? ORDER BY part_number",(uid,)).fetchall()
        if not u: raise StorageError("NoSuchUpload","The specified upload does not exist.",404)
        return u,p
    def complete(self,uid,requested):
        u,stored=self.parts(uid); by={r["part_number"]:r for r in stored}
        if not requested or any(n not in by or by[n]["etag"] != e for n,e in requested): raise StorageError("InvalidPart","One or more parts could not be found.",400)
        if len({n for n, _ in requested}) != len(requested): raise StorageError("InvalidPart", "A part may only appear once.", 400)
        if sum(by[n]["size"] for n, _ in requested) > self.max_object_size: raise StorageError("EntityTooLarge", "The completed object exceeds the configured maximum object size.", 413)
        tmp=self.files.new_temp()
        with tmp.open("wb") as out:
            for n,_ in requested:
                with open(by[n]["temp_path"],"rb") as f: shutil.copyfileobj(f,out)
        part_hash = __import__('hashlib').md5(usedforsecurity=False)
        for n,_ in requested:
            with open(by[n]['temp_path'],'rb') as f: part_hash.update(f.read())
        multipart_etag = '"' + __import__('hashlib').md5(b''.join(bytes.fromhex(by[n]['etag'].strip('"')) for n,_ in requested), usedforsecurity=False).hexdigest() + '-' + str(len(requested)) + '"'
        with tmp.open('r+b') as f: os.fsync(f.fileno())
        try:
            result=self.put_object(u["bucket"],u["object_key"],tmp,u['content_type'],json.loads(u['metadata']))
            with self.db.transaction() as c: c.execute("UPDATE objects SET etag=? WHERE bucket=? AND key=?",(multipart_etag,u['bucket'],u['object_key']))
            result=self.get_object(u['bucket'],u['object_key'])[0]
            with self.db.transaction() as c: c.execute("UPDATE multipart_uploads SET status='completed' WHERE upload_id=?",(uid,))
            return result
        finally:
            self.files.remove(tmp); shutil.rmtree(self.files.multipart/uid,ignore_errors=True)
    def abort(self,uid):
        with self.db.transaction() as c: c.execute("DELETE FROM multipart_uploads WHERE upload_id=?",(uid,))
        shutil.rmtree(self.files.multipart/uid,ignore_errors=True)
