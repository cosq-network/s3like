FROM python:3.12-slim
WORKDIR /app
ARG VCS_REF=unknown
ARG BUILD_VERSION=unknown
ARG BUILD_DATE=unknown
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app /app/app
EXPOSE 9000 9001
LABEL org.opencontainers.image.source="https://github.com/cosqnetwork/s3like" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.version="$BUILD_VERSION" \
      org.opencontainers.image.created="$BUILD_DATE"
ENV DATA_DIR=/data S3_ACCESS_KEY_ID=dev-access S3_SECRET_ACCESS_KEY=dev-secret S3_REGION=us-east-1 S3_BUCKET_NAME=dev-bucket S3_AUTO_CREATE_BUCKET=true S3_DEVELOPMENT_MODE=true
VOLUME ["/data"]
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=12 CMD python -c "import urllib.request; [urllib.request.urlopen(u, timeout=2).read() for u in ('http://127.0.0.1:9000/health/ready','http://127.0.0.1:9001/health/live')]"
CMD ["python", "-m", "app.container"]
