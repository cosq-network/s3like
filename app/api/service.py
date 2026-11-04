import os,re,email.utils,shutil,urllib.parse,json,logging,time,uuid
from datetime import datetime,timezone
from urllib.parse import unquote
from quart import Blueprint, request, Response, jsonify, g
from .auth import validate_with_error
from .xml import response,error
from app.storage import StorageService,StorageError

BUCKET=re.compile(r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$')
def _date(s): return email.utils.format_datetime(datetime.fromisoformat(s),usegmt=True)
def _valid_bucket(b): return bool(BUCKET.match(b)) and not ('..' in b or '.-' in b or '-.' in b)
def _range(value,size):
    if not value or not value.startswith('bytes='): return None
    a,b=value[6:].split('-',1)
    try:
        if a: start=int(a); end=int(b) if b else size-1
        else: end=size-1; start=max(0,size-int(b))
        if start<0 or end<start or start>=size: return None
        return start,min(end,size-1)
    except ValueError: return None
async def _temp(storage, limit=None):
    limit = limit or storage.max_request_size
    length = request.content_length
    if length is not None and length > limit: raise StorageError('EntityTooLarge','Your proposed upload exceeds the maximum allowed object size.',413)
    p=storage.files.new_temp(); total=0
    try:
        async for chunk in request.body:
            total += len(chunk)
            if total > limit: raise StorageError('EntityTooLarge','Your proposed upload exceeds the maximum allowed object size.',413)
            with p.open('ab') as f: f.write(chunk)
        return p
    except Exception:
        storage.files.remove(p); raise
def create_api(storage:StorageService):
    bp=Blueprint('s3',__name__)
    counters={'requests':0,'errors':0}
    logger=logging.getLogger('s3like.request')
    @bp.after_request
    async def request_log(resp):
        started=getattr(g, 's3_started', time.perf_counter())
        g.s3_duration_ms=f'{(time.perf_counter()-started)*1000:.2f}'
        if resp.status_code >= 400: counters['errors'] += 1
        logger.info('s3_request request_id=%s method=%s path=%s operation=%s bucket=%s status=%s duration_ms=%s error_code=%s',
                    getattr(g, 's3_request_id', '-'), request.method, request.path,
                    request.args.get('uploads') and 'CreateMultipartUpload' or request.method,
                    request.path.strip('/').split('/',1)[0] if request.path.strip('/') else '-', resp.status_code,
                    getattr(g, 's3_duration_ms', '0'), resp.headers.get('x-amz-error-code','-'))
        return resp
    @bp.before_request
    async def request_context():
        g.s3_request_id=request.headers.get('x-request-id',uuid.uuid4().hex)
        g.s3_started=time.perf_counter()
    @bp.before_request
    async def auth():
        counters['requests'] += 1
        if request.path.startswith(('/health/','/minio/health/')): return None
        ok, code = validate_with_error()
        if not ok: return error(code,'The authorization mechanism you have provided is not supported. Please use AWS4-HMAC-SHA256.',403)
    @bp.errorhandler(StorageError)
    async def storage_error(e): return error(e.code,e.message,e.status)
    @bp.get('/health/live')
    async def live(): return jsonify(status='ok')
    @bp.get('/health/ready')
    async def ready():
        try:
            storage.db.initialize()
            if not getattr(storage, '_ready', True): raise RuntimeError('storage initialization pending')
            return jsonify(status='ok')
        except Exception: return jsonify(status='not_ready'),503
    @bp.get('/minio/health/live')
    async def minio_live(): return Response(status=200)
    @bp.get('/minio/health/ready')
    async def minio_ready(): return Response(status=200)
    @bp.get('/metrics')
    async def metrics(): return jsonify(**counters, buckets=len(storage.list_buckets()))
    @bp.get('/')
    async def list_buckets():
        return response('ListAllMyBucketsResult',{'Owner':{'ID':'s3like','DisplayName':'s3like'},'Buckets':[{'Name':r['name'],'CreationDate':_date(r['created_at'])} for r in storage.list_buckets()]})
    @bp.route('/<bucket>',methods=['PUT','HEAD','GET','DELETE','POST'])
    async def bucket_route(bucket):
        if not _valid_bucket(bucket): return error('InvalidBucketName','The specified bucket is not valid.',400)
        if request.method=='PUT': storage.create_bucket(bucket); return Response(status=200)
        if request.method=='HEAD': storage.require_bucket(bucket); return Response(status=200)
        if request.method=='DELETE': storage.delete_bucket(bucket); return Response(status=204)
        if request.method=='POST' and 'delete' in request.args:
            from xml.etree.ElementTree import fromstring
            root=fromstring(await request.get_data()); deleted=[]
            for item in root.iter():
                if item.tag.rsplit('}',1)[-1] != 'Object': continue
                key=next((child.text for child in item if child.tag.rsplit('}',1)[-1] == 'Key'), None)
                if key:
                    try: storage.delete_object(bucket,key); deleted.append({'Key':key})
                    except StorageError as exc:
                        if exc.code != 'NoSuchKey': raise
            return response('DeleteResult',{'Deleted':deleted})
        if request.method=='POST': return error('NotImplemented','The requested operation is not implemented.',501)
        if request.args.get('encoding-type') not in (None,'url'): return error('InvalidArgument','Invalid encoding-type.',400)
        try: max_keys=min(max(int(request.args.get('max-keys','1000')),0),1000)
        except ValueError: return error('InvalidArgument','Invalid max-keys.',400)
        rows,prefixes,truncated,nextkey=storage.list_objects(bucket,request.args.get('prefix',''),request.args.get('delimiter'),request.args.get('start-after',''),request.args.get('continuation-token'),max_keys)
        enc=lambda x: urllib.parse.quote(str(x),safe='') if request.args.get('encoding-type')=='url' else str(x)
        data={'Name':bucket,'Prefix':enc(request.args.get('prefix','')),'KeyCount':len(rows)+len(prefixes),'MaxKeys':max_keys,'StartAfter':enc(request.args.get('start-after','')) if request.args.get('start-after') else None,'IsTruncated':str(truncated).lower(),'NextContinuationToken':nextkey if truncated else None,'Contents':[{'Key':enc(r['key']),'LastModified':_date(r['last_modified']),'ETag':r['etag'],'Size':r['size'],'StorageClass':'STANDARD',**({'Owner':{'ID':'s3like','DisplayName':'s3like'}} if request.args.get('fetch-owner')=='true' else {})} for r in rows],'CommonPrefixes':[{'Prefix':enc(p)} for p in prefixes]}
        return response('ListBucketResult',data)
    @bp.route('/<bucket>/<path:key>',methods=['PUT','GET','HEAD','DELETE','POST'])
    async def object_route(bucket,key):
        key=unquote(key)
        if len(key)>1024: return error('InvalidRequest','Object key is too long.',400)
        if request.method=='PUT' and request.args.get('partNumber') and request.args.get('uploadId'):
            try: number=int(request.args['partNumber'])
            except ValueError: return error('InvalidArgument','Invalid part number.',400)
            if not 1 <= number <= 10000: return error('InvalidArgument','Invalid part number.',400)
            p=await _temp(storage)
            try: etag=storage.upload_part(request.args['uploadId'],number,p)
            finally: storage.files.remove(p)
            return Response(status=200,headers={'ETag':etag})
        if request.method=='POST' and 'uploads' in request.args:
            metadata={k[11:]:v for k,v in request.headers.items() if k.lower().startswith('x-amz-meta-')}
            uid=storage.initiate(bucket,key,request.headers.get('Content-Type','application/octet-stream'),metadata); return response('InitiateMultipartUploadResult',{'Bucket':bucket,'Key':key,'UploadId':uid})
        if request.method=='GET' and request.args.get('uploadId'):
            u,parts=storage.parts(request.args['uploadId']); return response('ListPartsResult',{'Bucket':u['bucket'],'Key':u['object_key'],'UploadId':u['upload_id'],'Part':[{'PartNumber':p['part_number'],'LastModified':u['initiated'],'ETag':p['etag'],'Size':p['size']} for p in parts]})
        if request.method=='DELETE' and request.args.get('uploadId'): storage.abort(request.args['uploadId']); return Response(status=204)
        if request.method=='POST' and request.args.get('uploadId'):
            from xml.etree.ElementTree import fromstring
            root=fromstring(await request.get_data()); parts=[]
            for x in root.iter():
                if x.tag.rsplit('}',1)[-1] != 'Part': continue
                values={child.tag.rsplit('}',1)[-1]:child.text for child in x}
                parts.append((int(values['PartNumber']),values['ETag']))
            r=storage.complete(request.args['uploadId'],parts); return response('CompleteMultipartUploadResult',{'Location':f'/{bucket}/{key}','Bucket':bucket,'Key':key,'ETag':r['etag']})
        if request.method=='POST': return error('NotImplemented','The requested operation is not implemented.',501)
        if request.method=='DELETE': storage.delete_object(bucket,key); return Response(status=204)
        if request.method=='PUT':
            if request.headers.get('x-amz-copy-source'):
                src=request.headers['x-amz-copy-source'].lstrip('/').split('/',1); r=storage.copy_object(bucket,key,src[0],unquote(src[1])); return response('CopyObjectResult',{'LastModified':_date(r['last_modified']),'ETag':r['etag']})
            p=await _temp(storage, storage.max_object_size); metadata={k[11:]:v for k,v in request.headers.items() if k.lower().startswith('x-amz-meta-')}
            try: r=storage.put_object(bucket,key,p,request.headers.get('Content-Type','application/octet-stream'),metadata)
            finally: storage.files.remove(p)
            return Response(status=200,headers={'ETag':r['etag']})
        r,path=storage.get_object(bucket,key); headers={'ETag':r['etag'],'Last-Modified':_date(r['last_modified']),'Content-Length':str(r['size']),'Content-Type':r['content_type'],'Accept-Ranges':'bytes'}
        try: headers.update({'x-amz-meta-'+k:v for k,v in json.loads(r['metadata']).items()})
        except (KeyError,TypeError,json.JSONDecodeError): pass
        if request.headers.get('If-Match') and request.headers['If-Match']!=r['etag']: return Response(status=412,headers=headers)
        if request.headers.get('If-None-Match')==r['etag']: return Response(status=304,headers=headers)
        try:
            modified=datetime.fromisoformat(r['last_modified'])
            if request.headers.get('If-Modified-Since') and modified <= email.utils.parsedate_to_datetime(request.headers['If-Modified-Since']): return Response(status=304,headers=headers)
            if request.headers.get('If-Unmodified-Since') and modified > email.utils.parsedate_to_datetime(request.headers['If-Unmodified-Since']): return Response(status=412,headers=headers)
        except (TypeError,ValueError): pass
        if request.method=='HEAD': return Response(status=200,headers=headers)
        rg=_range(request.headers.get('Range'),r['size'])
        if request.headers.get('Range') and not rg: return Response(status=416,headers={**headers,'Content-Range':f'bytes */{r["size"]}'})
        if rg:
            start,end=rg; f=path.open('rb'); f.seek(start); body=f.read(end-start+1); f.close(); headers.update({'Content-Length':str(len(body)),'Content-Range':f'bytes {start}-{end}/{r["size"]}'}); return Response(body,status=206,headers=headers)
        return Response(path.read_bytes(),headers=headers)
    return bp
