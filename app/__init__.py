from quart import Quart, render_template, request, redirect, url_for, Response, jsonify
import re
from .config import Config
from .storage import StorageService
from .api.service import create_api

def create_s3_app(config_obj=Config):
    cfg=config_obj()
    if not cfg.DEVELOPMENT_MODE and (cfg.S3_ACCESS_KEY_ID, cfg.S3_SECRET_ACCESS_KEY) in {
        ('testkey','testsecret'), ('minio','minio123'), ('dev-access','dev-secret')
    }:
        raise RuntimeError('Default credentials are not allowed outside development mode')
    app=Quart(__name__); app.config.from_object(cfg); app.storage=StorageService(cfg.data_path,cfg.S3_MULTIPART_RETENTION_HOURS,cfg.S3_MAX_OBJECT_SIZE,cfg.S3_MAX_REQUEST_SIZE); app.storage._ready=False
    @app.before_serving
    async def initialize_storage():
        app.storage.db.initialize()
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', cfg.S3_BUCKET_NAME or '') or '..' in cfg.S3_BUCKET_NAME or '.-' in cfg.S3_BUCKET_NAME or '-.' in cfg.S3_BUCKET_NAME:
            raise RuntimeError('Configured S3_BUCKET_NAME is invalid')
        if cfg.S3_AUTO_CREATE_BUCKET:
            app.storage.ensure_bucket(cfg.S3_BUCKET_NAME)
        app.storage._ready=True
    app.register_blueprint(create_api(app.storage)); return app

def create_console_app(config_obj=Config):
    cfg=config_obj(); app=Quart(__name__); app.config.from_object(cfg); app.storage=StorageService(cfg.data_path,cfg.S3_MULTIPART_RETENTION_HOURS,cfg.S3_MAX_OBJECT_SIZE,cfg.S3_MAX_REQUEST_SIZE)
    @app.before_serving
    async def initialize_console_storage():
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', cfg.S3_BUCKET_NAME or '') or '..' in cfg.S3_BUCKET_NAME or '.-' in cfg.S3_BUCKET_NAME or '-.' in cfg.S3_BUCKET_NAME:
            raise RuntimeError('Configured S3_BUCKET_NAME is invalid')
        if cfg.S3_AUTO_CREATE_BUCKET:
            app.storage.ensure_bucket(cfg.S3_BUCKET_NAME)
    @app.before_request
    async def console_auth():
        if cfg.CONSOLE_USERNAME and cfg.CONSOLE_PASSWORD:
            import base64
            expected='Basic '+base64.b64encode(f'{cfg.CONSOLE_USERNAME}:{cfg.CONSOLE_PASSWORD}'.encode()).decode()
            if request.headers.get('Authorization') != expected:
                return Response('Authentication required',401,headers={'WWW-Authenticate':'Basic realm="S3Like Console"'})
    @app.get('/')
    async def index(): return await render_template('console.html',buckets=app.storage.list_buckets())
    @app.post('/bucket/create')
    async def create_bucket():
        form=await request.form; name=(form.get('name') or '').strip()
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',name) or '..' in name or '.-' in name or '-.' in name:
            return 'Invalid bucket name',400
        try: app.storage.create_bucket(name)
        except Exception as exc: return str(exc),getattr(exc,'status',500)
        return redirect(url_for('index'))
    @app.post('/bucket/<bucket>/delete')
    async def delete_bucket(bucket):
        try: app.storage.delete_bucket(bucket)
        except Exception as exc: return str(exc),getattr(exc,'status',500)
        return redirect(url_for('index'))
    @app.get('/bucket/<bucket>')
    async def bucket(bucket):
        try: rows,_,_,_=app.storage.list_objects(bucket)
        except Exception as exc: return str(exc),getattr(exc,'status',404)
        return await render_template('bucket.html',bucket=bucket,objects=rows)
    @app.post('/bucket/<bucket>/upload')
    async def upload(bucket):
        f=(await request.files).get('file')
        if not f or not f.filename: return 'No file selected',400
        p=app.storage.files.new_temp()
        try:
            await f.save(p); app.storage.put_object(bucket,f.filename,p,f.content_type or 'application/octet-stream')
        except Exception as exc:
            app.storage.files.remove(p); return str(exc),getattr(exc,'status',500)
        return redirect(url_for('bucket',bucket=bucket))
    @app.get('/bucket/<bucket>/download/<path:key>')
    async def download(bucket,key):
        from quart import send_file
        _,p=app.storage.get_object(bucket,key); return await send_file(p,as_attachment=True,attachment_filename=key.rsplit('/',1)[-1])
    @app.get('/s3/<bucket>/<path:key>/presigned')
    async def presigned(bucket,key):
        import boto3
        from botocore.config import Config as BotoConfig
        url=boto3.client('s3', endpoint_url=cfg.S3_ENDPOINT_URL, region_name=cfg.S3_REGION,
                         aws_access_key_id=cfg.S3_ACCESS_KEY_ID, aws_secret_access_key=cfg.S3_SECRET_ACCESS_KEY,
                         config=BotoConfig(s3={'addressing_style':'path'})).generate_presigned_url(
                             'get_object', Params={'Bucket':bucket,'Key':key}, ExpiresIn=300)
        return jsonify(presigned_url=url)
    @app.post('/bucket/<bucket>/delete/<path:key>')
    async def delete(bucket,key): app.storage.delete_object(bucket,key); return redirect(url_for('bucket',bucket=bucket))
    @app.get('/health/live')
    async def health(): return {'status':'ok'}
    @app.get('/health')
    async def health_alias(): return {'status':'ok'}
    @app.get('/health/ready')
    async def console_ready(): return ({'status':'ok'},200) if app.storage.db.path.exists() else ({'status':'not_ready'},503)
    @app.get('/metrics')
    async def metrics():
        buckets=app.storage.list_buckets(); objects=sum(len(app.storage.list_objects(b['name'])[0]) for b in buckets)
        return jsonify(buckets=len(buckets),objects=objects)
    return app

def create_app(config_obj=Config):
    app=create_console_app(config_obj); app.register_blueprint(create_api(app.storage)); return app
