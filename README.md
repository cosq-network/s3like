# S3Like

S3Like is a lightweight, self-contained S3-compatible object storage service and web console packaged into a single Docker image. Built with Python and Quart (async), it runs as a unified container exposing both an S3 API endpoint and an administrative web console. It is designed specifically for local development, CI/CD testing, and integration environments.

---

## Architecture Overview

S3Like runs two coordinated async services managed by a built-in supervisor (`app.container`):

* **S3 API Server (`port 9000`)**: Handles AWS S3 REST/XML requests, SigV4 authentication, presigned URLs, streaming `aws-chunked` uploads, and multipart operations.
* **Web Console Server (`port 9001`)**: Provides an interactive browser UI for managing buckets and objects, with optional HTTP Basic Auth protection.
* **Storage Engine**: Persists all state to `$DATA_DIR` (`/data` in Docker, `./data` locally):
  * **Metadata Store**: SQLite database (`metadata/s3like.db`) tracking buckets, object metadata (size, ETag, content type, timestamps), and multipart upload sessions.
  * **Object Store**: Local filesystem structure separating committed objects (`objects/`), multipart parts in progress (`multipart/`), and temporary write buffers (`tmp/`). Automatic cleanup purges orphaned tmp files on failure and expires abandoned multipart uploads on startup.

```
       ┌────────────────────────────────────────────────────────┐
       │                   S3Like Container                     │
       │                                                        │
       │   [Port 9000] S3 API         [Port 9001] Web Console   │
       │   (Quart / REST / XML)        (Quart / Templates)      │
       │            │                           │               │
       │            └─────────────┬─────────────┘               │
       │                          ▼                             │
       │                 Storage Service Layer                  │
       │                 ┌────────┴────────┐                    │
       │                 ▼                 ▼                    │
       │           SQLite DB          Object Store              │
       │         (s3like.db)     (objects/, multipart/, tmp/)   │
       └─────────────────┼─────────────────┼────────────────────┘
                         ▼                 ▼
                     /data Volume (Named Docker Volume)
```

---

## Quick Start

```bash
docker compose up --build
```

Copy `.env.example` to `.env` to customize settings locally. The default endpoints are:
* **S3 API**: `http://localhost:${S3LIKE_API_PORT:-9000}`
* **Web Console**: `http://localhost:${S3LIKE_CONSOLE_PORT:-9001}`

Set `S3LIKE_API_PORT` and `S3LIKE_CONSOLE_PORT` in `.env` to rebind host ports without modifying container ports. Container-to-container clients on the same Docker network use `http://s3like:9000`.

Development defaults out-of-the-box:
* **Access Key ID**: `dev-access`
* **Secret Access Key**: `dev-secret`
* **Region**: `us-east-1`
* **Auto-created Bucket**: `dev-bucket`

To use a prebuilt image from Docker Hub, configure `S3LIKE_IMAGE`:
```bash
S3LIKE_IMAGE=cosqnetwork/s3like:0.1.1 docker compose up
```

Persistent data is stored in the named Docker volume `s3like-data`. To completely reset state:
```bash
docker compose down -v
```

An end-to-end multi-service consumer example is available in [examples/consumer-compose](examples/consumer-compose).

---

## Supported S3 API Features

* **Bucket Management**:
  * `CreateBucket` (`PUT /{bucket}`) — validates DNS-compliant bucket names.
  * `DeleteBucket` (`DELETE /{bucket}`) — enforces bucket emptiness.
  * `ListBuckets` (`GET /`) — returns AWS-compliant `ListAllMyBucketsResult` XML.
  * `HeadBucket` (`HEAD /{bucket}`) — checks bucket existence and readiness.
* **Object Management**:
  * `PutObject` (`PUT /{bucket}/{key}`) — stores payload, computes MD5/ETag, preserves custom metadata and MIME type.
  * `GetObject` (`GET /{bucket}/{key}`) — returns raw object bytes, headers, and metadata.
  * `HeadObject` (`HEAD /{bucket}/{key}`) — returns object headers and size without body.
  * `DeleteObject` (`DELETE /{bucket}/{key}`) — deletes object and metadata.
  * `CopyObject` (`PUT /{bucket}/{key}` with `x-amz-copy-source`) — server-side copy preserving or replacing metadata.
* **AWS SDK `aws-chunked` Streaming Uploads**:
  * Decodes streaming chunk framing sent by AWS SDKs (e.g. AWS SDK for .NET, Java, Go) when `x-amz-content-sha256` starts with `STREAMING-` or `Content-Encoding: aws-chunked`.
  * Strips chunk length headers, signatures, and checksum trailers (`x-amz-checksum-crc32`, `x-amz-trailer-signature`) on the fly so pure object bytes are stored without payload corruption.
  * Validates `x-amz-decoded-content-length` and rejects truncated/malformed streams with 400 Bad Request.
* **Multipart Upload Lifecycle**:
  * `InitiateMultipartUpload` (`POST /{bucket}/{key}?uploads`) — initializes upload session and returns `UploadId`.
  * `UploadPart` (`PUT /{bucket}/{key}?partNumber={n}&uploadId={id}`) — uploads numbered parts (supports raw bytes and `aws-chunked` streams).
  * `ListParts` (`GET /{bucket}/{key}?uploadId={id}`) — lists uploaded parts.
  * `CompleteMultipartUpload` (`POST /{bucket}/{key}?uploadId={id}`) — validates part sequences, concatenates parts atomically, and generates combined ETag.
  * `AbortMultipartUpload` (`DELETE /{bucket}/{key}?uploadId={id}`) — cancels session and purges staged parts.
* **Advanced HTTP Reads**:
  * **Range Requests**: Supports `Range: bytes=start-end` with `206 Partial Content` responses.
  * **Conditional Headers**: Supports `If-Match`, `If-None-Match`, `If-Modified-Since`, and `If-Unmodified-Since`.
* **Authentication & Security**:
  * **AWS SigV4 Authentication**: Verifies `AWS4-HMAC-SHA256` signatures against configured credentials.
  * **Presigned URLs**: Supports presigned GET and PUT URLs using query parameters (`X-Amz-Algorithm`, `X-Amz-Credential`, `X-Amz-Date`, `X-Amz-Expires`, `X-Amz-Signature`).
  * **Development Mode**: In development mode (`S3_DEVELOPMENT_MODE=true`), default development credentials are permitted. In production mode, default credentials are strictly rejected.
* **Health Checks**:
  * S3 API: `GET /health/live`, `GET /health/ready`, `GET /minio/health/live`, `GET /minio/health/ready`.
  * Web Console: `GET /health/live`.
  * The Docker container healthcheck verifies both API readiness and console liveness.

> [!NOTE]
> S3Like is designed for local development and test environments. It does not implement distributed clustering, erasure coding, versioning, bucket policies, object locking, lifecycle rules, replication, or MinIO admin APIs. For data migration, use standard S3 tools such as `aws s3 sync`.

---

## AWS Client Usage

Always configure **path-style addressing** when interacting with local endpoints.

### AWS CLI

```bash
export AWS_ACCESS_KEY_ID=dev-access
export AWS_SECRET_ACCESS_KEY=dev-secret
export AWS_DEFAULT_REGION=us-east-1

# List buckets
aws --endpoint-url http://localhost:9000 s3 ls

# Upload file
aws --endpoint-url http://localhost:9000 s3 cp ./sample.txt s3://dev-bucket/sample.txt

# Download file
aws --endpoint-url http://localhost:9000 s3 cp s3://dev-bucket/sample.txt ./download.txt
```

### Python (boto3)

```python
import boto3
from botocore.config import Config

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="dev-access",
    aws_secret_access_key="dev-secret",
    region_name="us-east-1",
    config=Config(s3={"addressing_style": "path"}),
)

# Upload an object
s3.put_object(Bucket="dev-bucket", Key="hello.txt", Body=b"Hello S3Like!", ContentType="text/plain")

# Generate presigned download URL
url = s3.generate_presigned_url("get_object", Params={"Bucket": "dev-bucket", "Key": "hello.txt"}, ExpiresIn=300)
print("Presigned URL:", url)
```

### .NET / C# (AWS SDK for .NET)

```csharp
using Amazon.S3;
using Amazon.S3.Model;

var config = new AmazonS3Config
{
    ServiceURL = "http://localhost:9000",
    ForcePathStyle = true,
    AuthenticationRegion = "us-east-1"
};

using var client = new AmazonS3Client("dev-access", "dev-secret", config);

// Upload (SDK automatically streams with aws-chunked encoding)
await client.PutObjectAsync(new PutObjectRequest
{
    BucketName = "dev-bucket",
    Key = "document.pdf",
    FilePath = "./document.pdf"
});
```

---

## Configuration Reference

All settings are configured via environment variables. `S3_*` variables take precedence over legacy MinIO and AWS aliases.

| Environment Variable | Default | Aliases / Fallbacks | Description |
|---|---|---|---|
| `S3LIKE_IMAGE` | `s3like:dev` | — | Docker image tag used by Compose |
| `S3LIKE_API_PORT` | `9000` | — | Host port mapping for S3 API |
| `S3LIKE_CONSOLE_PORT` | `9001` | — | Host port mapping for Web Console |
| `DATA_DIR` | `/data` (container) / `./data` (local) | `MINIO_VOLUMES` | Storage directory for metadata DB and object files |
| `S3_ACCESS_KEY_ID` | `dev-access` | `MINIO_ROOT_USER`, `AWS_ACCESS_KEY_ID` | S3 API Access Key ID |
| `S3_SECRET_ACCESS_KEY` | `dev-secret` | `MINIO_ROOT_PASSWORD`, `AWS_SECRET_ACCESS_KEY` | S3 API Secret Access Key |
| `S3_REGION` | `us-east-1` | `MINIO_REGION` | AWS region name |
| `S3_BUCKET_NAME` | `dev-bucket` | `MINIO_BUCKET_NAME` | Default bucket provisioned on startup |
| `S3_AUTO_CREATE_BUCKET` | `true` | — | Automatically create default bucket if not present |
| `S3_DEVELOPMENT_MODE` | `true` | `DEVELOPMENT_MODE` | Enables dev credentials; set `false` for strict production mode |
| `S3_MAX_OBJECT_SIZE` | `5368709120` (5 GB) | — | Maximum allowed single object size in bytes |
| `S3_MAX_REQUEST_SIZE` | `5368709120` (5 GB) | — | Maximum allowed HTTP request body size in bytes |
| `S3_MULTIPART_RETENTION_HOURS` | `24` | — | Hours before active uncompleted multipart uploads expire |
| `CONSOLE_USERNAME` | *(empty)* | — | Basic Auth username for Web Console (auth disabled if empty) |
| `CONSOLE_PASSWORD` | *(empty)* | — | Basic Auth password for Web Console |

---

## Running Tests

### Unit Tests
```bash
python -m pytest tests/unit
```
Verifies configuration parsing, container supervisor wiring, storage operations, XML rendering, SigV4 authentication, and `aws-chunked` framing decoders.

### Integration Tests
```bash
python -m pytest tests/integration
```
Runs end-to-end API workflows including bucket creation, object CRUD, range reads, copy operations, `aws-chunked` streaming uploads, multipart lifecycle, and console routes.

### Web Console UI Tests (Playwright)
```bash
cd playwright_tests
npx playwright test
```
Runs browser-driven end-to-end tests verifying console bucket listing, navigation, and file uploads.

---

## Release Process

The version source of truth is [`app/version.py`](file:///C:/Projects/s3like/app/version.py):

```python
__version__ = "0.1.1"
```

1. Bump `__version__` in `app/version.py` and commit the change.
2. Push a strict version tag matching `vX.Y.Z` (e.g., `git tag v0.1.1 && git push origin v0.1.1`).
3. GitHub Actions (`.github/workflows/docker.yml`) validates the tag against `app/version.py`, runs compilation and all tests, performs a Docker health smoke test, and publishes both `cosqnetwork/s3like:X.Y.Z` and `cosqnetwork/s3like:latest` to Docker Hub.
