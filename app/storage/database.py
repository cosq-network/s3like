import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version(version) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
CREATE TABLE IF NOT EXISTS buckets (name TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS objects (bucket TEXT NOT NULL REFERENCES buckets(name) ON DELETE CASCADE, key TEXT NOT NULL, storage_id TEXT NOT NULL, size INTEGER NOT NULL, etag TEXT NOT NULL, content_type TEXT NOT NULL, last_modified TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(bucket,key));
CREATE INDEX IF NOT EXISTS idx_objects_bucket_key ON objects(bucket,key);
CREATE TABLE IF NOT EXISTS multipart_uploads (upload_id TEXT PRIMARY KEY, bucket TEXT NOT NULL REFERENCES buckets(name) ON DELETE CASCADE, object_key TEXT NOT NULL, initiated TEXT NOT NULL, status TEXT NOT NULL, content_type TEXT NOT NULL DEFAULT 'application/octet-stream', metadata TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS multipart_parts (upload_id TEXT NOT NULL REFERENCES multipart_uploads(upload_id) ON DELETE CASCADE, part_number INTEGER NOT NULL, temp_path TEXT NOT NULL, size INTEGER NOT NULL, etag TEXT NOT NULL, PRIMARY KEY(upload_id,part_number));
CREATE INDEX IF NOT EXISTS idx_parts_upload_part ON multipart_parts(upload_id,part_number);
CREATE TABLE IF NOT EXISTS access_keys (access_key_id TEXT PRIMARY KEY, secret_reference TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
"""

class Database:
    def __init__(self, path: Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self.initialize()
    def connect(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None); c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA busy_timeout=30000"); c.execute("PRAGMA synchronous=FULL"); return c
    def initialize(self):
        with self.connect() as c:
            c.executescript(SCHEMA)
            for sql in ("ALTER TABLE objects ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'", "ALTER TABLE multipart_uploads ADD COLUMN content_type TEXT NOT NULL DEFAULT 'application/octet-stream'", "ALTER TABLE multipart_uploads ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'"):
                try: c.execute(sql)
                except sqlite3.OperationalError:
                    pass
    @contextmanager
    def transaction(self):
        c = self.connect()
        try: c.execute("BEGIN IMMEDIATE"); yield c; c.commit()
        except Exception: c.rollback(); raise
        finally: c.close()
