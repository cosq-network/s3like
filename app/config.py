import os
from pathlib import Path

def _int(name, default):
    try: return int(os.getenv(name, default))
    except (TypeError, ValueError): return default

def _bool(name, default=False):
    value = os.getenv(name)
    return default if value is None else value.lower() in ('1','true','yes','on')

class Config:
    def __init__(self):
        self.SECRET_KEY=os.getenv('SECRET_KEY','super-secret-key-change-me'); self.FLASK_ENV=os.getenv('FLASK_ENV','development')
        mode=os.getenv('S3_DEVELOPMENT_MODE', os.getenv('DEVELOPMENT_MODE', 'true' if self.FLASK_ENV == 'development' else ''))
        self.DEVELOPMENT_MODE=mode.lower() in ('1','true','yes','on')
        self.DATA_DIR=os.getenv('DATA_DIR') or os.getenv('MINIO_VOLUMES','./data').split(',')[0].replace('/data','./data')
        self.S3_LISTEN_HOST=os.getenv('S3_LISTEN_HOST','0.0.0.0'); self.S3_LISTEN_PORT=_int('S3_LISTEN_PORT',9000)
        self.CONSOLE_LISTEN_HOST=os.getenv('CONSOLE_LISTEN_HOST','0.0.0.0'); self.CONSOLE_PORT=_int('CONSOLE_PORT',9001)
        self.S3_REGION=os.getenv('S3_REGION') or os.getenv('MINIO_REGION','us-east-1'); self.S3_SERVICE=os.getenv('S3_SERVICE','s3'); self.S3_BUCKET_NAME=os.getenv('S3_BUCKET_NAME') or os.getenv('MINIO_BUCKET_NAME','dev-bucket')
        self.S3_AUTO_CREATE_BUCKET=_bool('S3_AUTO_CREATE_BUCKET', True)
        self.S3_ENDPOINT_URL=os.getenv('S3_ENDPOINT_URL') or os.getenv('MINIO_SERVER_URL','http://localhost:9000'); self.S3_USE_SSL=os.getenv('S3_USE_SSL','false').lower() in ('1','true','yes')
        self.S3_ACCESS_KEY_ID=os.getenv('S3_ACCESS_KEY_ID') or os.getenv('MINIO_ROOT_USER') or os.getenv('AWS_ACCESS_KEY_ID','dev-access'); self.S3_SECRET_ACCESS_KEY=os.getenv('S3_SECRET_ACCESS_KEY') or os.getenv('MINIO_ROOT_PASSWORD') or os.getenv('AWS_SECRET_ACCESS_KEY','dev-secret')
        self.S3_MAX_OBJECT_SIZE=_int('S3_MAX_OBJECT_SIZE',5*1024*1024*1024); self.S3_MAX_REQUEST_SIZE=_int('S3_MAX_REQUEST_SIZE',5*1024*1024*1024); self.S3_MULTIPART_RETENTION_HOURS=_int('S3_MULTIPART_RETENTION_HOURS',24)
        self.CONSOLE_USERNAME=os.getenv('CONSOLE_USERNAME',''); self.CONSOLE_PASSWORD=os.getenv('CONSOLE_PASSWORD','')
        self.MINIO_BROWSER=_bool('MINIO_BROWSER', True)
    @property
    def data_path(self): return Path(self.DATA_DIR).resolve()
    @property
    def db_path(self): return self.data_path/'metadata'/'s3like.db'
