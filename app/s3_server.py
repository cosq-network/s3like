from . import create_s3_app
from .config import Config
app=create_s3_app()
if __name__ == '__main__': app.run(host=Config().S3_LISTEN_HOST,port=Config().S3_LISTEN_PORT)
