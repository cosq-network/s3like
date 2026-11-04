# S3Like

S3Like is distributed as one Docker image and runs as one container exposing
both the S3 API and web console. It is designed for local development and
integration testing, not distributed production storage.

## Quick start

```bash
docker compose up --build
```

Copy `.env.example` to `.env` to keep overrides in a local file. The host
endpoints default to `http://localhost:${S3LIKE_API_PORT:-9000}` (S3 API) and
`http://localhost:${S3LIKE_CONSOLE_PORT:-9001}` (console); set
`S3LIKE_API_PORT` and `S3LIKE_CONSOLE_PORT` to change only the host ports.
Container-to-container clients use `http://s3like:9000`.

The local-only development defaults are credentials `dev-access` /
`dev-secret`, region `us-east-1`, and auto-created bucket `dev-bucket`.
To use a prebuilt image, set `S3LIKE_IMAGE` (for example,
`S3LIKE_IMAGE=cosqnetwork/s3like:0.2.0`) and run `docker compose up`.

Other Compose services connect to `http://s3like:9000`, not localhost. The
complete external integration example is in [examples/consumer-compose](examples/consumer-compose).

The named `s3like-data` volume persists metadata and objects across
`docker compose down`. To intentionally reset development state, run
`docker compose down -v`.

## Releases

`app/version.py` is the release version source. To prepare a release, update
`__version__`, commit that change, and push a matching strict version tag such
as `v0.2.0`. The tag triggers validation and publishes both
`cosqnetwork/s3like:0.2.0` and `cosqnetwork/s3like:latest` to Docker Hub.

Only version-tagged releases update `latest`. Ordinary pushes to `main` and
`release/**` run validation but do not publish images. The repository's Actions
secrets must include `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`.

## Configuration

The `.env.example` template documents the complete Compose configuration:
`S3LIKE_IMAGE` (`s3like:dev`), `S3LIKE_API_PORT` (`9000`),
`S3LIKE_CONSOLE_PORT` (`9001`), `DATA_DIR` (`/data`),
`S3_ACCESS_KEY_ID` (`dev-access`), `S3_SECRET_ACCESS_KEY` (`dev-secret`),
`S3_REGION` (`us-east-1`), `S3_BUCKET_NAME` (`dev-bucket`),
`S3_AUTO_CREATE_BUCKET` (`true`), `S3_DEVELOPMENT_MODE` (`true`),
`S3_MAX_OBJECT_SIZE` and `S3_MAX_REQUEST_SIZE` (`5368709120` each),
`S3_MULTIPART_RETENTION_HOURS` (`24`), and blank `CONSOLE_USERNAME` and
`CONSOLE_PASSWORD`. `DATA_DIR=/data` is the fixed container path backed by
the named volume. Explicit `S3_*` values take
precedence over MinIO-compatible aliases and AWS-compatible aliases. Production
mode rejects known development credentials.

Set both console credentials to enable Basic Auth. Health endpoints are
`/health/live`, `/health/ready`, `/minio/health/live`, and
`/minio/health/ready`; the container health check requires API readiness and
console liveness.

## AWS clients

Use path-style addressing for local endpoints:

```bash
export AWS_ACCESS_KEY_ID=dev-access AWS_SECRET_ACCESS_KEY=dev-secret AWS_DEFAULT_REGION=us-east-1
aws --endpoint-url http://localhost:9000 s3 ls
aws --endpoint-url http://localhost:9000 s3 cp ./file.bin s3://dev-bucket/file.bin
aws --endpoint-url http://localhost:9000 s3 cp s3://dev-bucket/file.bin ./download.bin
```

```python
import boto3
from botocore.config import Config
s3 = boto3.client("s3", endpoint_url="http://localhost:9000",
    aws_access_key_id="dev-access", aws_secret_access_key="dev-secret",
    region_name="us-east-1", config=Config(s3={"addressing_style": "path"}))
s3.put_object(Bucket="dev-bucket", Key="hello.txt", Body=b"hello", ContentType="text/plain")
url = s3.generate_presigned_url("get_object", Params={"Bucket":"dev-bucket", "Key":"hello.txt"}, ExpiresIn=300)
```

Bucket/object CRUD, metadata, content types, range and conditional reads,
copy/delete, SigV4, presigned URLs, and multipart upload/list/complete/abort
are supported. Uploads are bounded by the configured request and object size
limits; temporary files are cleaned on failure and expired multipart uploads
are cleaned on startup.

This is not full AWS S3 or MinIO compatibility. MinIO's internal disk format,
admin API, versioning, lifecycle, replication, object locking, notifications,
and distributed erasure coding are unsupported. Migrate through S3 APIs such as
`aws s3 sync`.

## Troubleshooting

- Port conflict: set `S3LIKE_API_PORT` or `S3LIKE_CONSOLE_PORT` in `.env`.
- Unhealthy startup: inspect `docker compose logs s3like`; API readiness includes
  SQLite initialization and bucket provisioning.
- Credential mismatch: configure access and secret values together.
- Stale state: use `docker compose down -v` only when deleting the named volume
  is intended.
