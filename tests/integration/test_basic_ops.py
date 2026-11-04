import io
import pytest
from app.config import Config
from werkzeug.datastructures import FileStorage

@pytest.mark.asyncio
async def test_upload_download_presigned(client):
    bucket = Config().S3_BUCKET_NAME
    resp = await client.post(f"/bucket/{bucket}/upload", files={"file": FileStorage(stream=io.BytesIO(b"Hello, S3 compatible world!"), filename="test.txt")})
    assert resp.status_code == 302
    resp = await client.get(f"/bucket/{bucket}")
    assert resp.status_code == 200 and "test.txt" in await resp.get_data(as_text=True)
    dl_resp = await client.get(f"/s3/{bucket}/test.txt/presigned")
    assert dl_resp.status_code == 200 and "presigned_url" in await dl_resp.get_json()

@pytest.mark.asyncio
async def test_delete_file(client):
    bucket = Config().S3_BUCKET_NAME
    resp = await client.post(f"/bucket/{bucket}/upload", files={"file": FileStorage(stream=io.BytesIO(b"Delete me!"), filename="to_delete.txt")})
    assert resp.status_code == 302
    assert (await client.post(f"/bucket/{bucket}/delete/to_delete.txt")).status_code == 302
    resp = await client.get(f"/bucket/{bucket}")
    assert "to_delete.txt" not in await resp.get_data(as_text=True)

@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert await resp.get_json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_s3_bucket_and_object_flow(client):
    bucket = "integration-bucket"
    assert (await client.put(f"/{bucket}")).status_code == 200
    put = await client.put(f"/{bucket}/hello.txt", data=b"hello", headers={"Content-Type": "text/plain", "x-amz-meta-owner": "test"})
    assert put.status_code == 200
    get = await client.get(f"/{bucket}/hello.txt", headers={"Range": "bytes=1-3"})
    assert get.status_code == 206 and await get.get_data() == b"ell"
    assert get.headers["Content-Range"] == "bytes 1-3/5"
    head = await client.head(f"/{bucket}/hello.txt")
    assert head.headers["Content-Type"] == "text/plain" and head.headers["x-amz-meta-owner"] == "test"
    assert (await client.delete(f"/{bucket}/hello.txt")).status_code == 204
    assert (await client.delete(f"/{bucket}")).status_code == 204

@pytest.mark.asyncio
async def test_health_readiness_and_missing_bucket(client):
    assert (await client.get("/health/live")).status_code == 200
    assert (await client.get("/health/ready")).status_code == 200
    response = await client.get("/missing-bucket/nope")
    assert response.status_code == 404
    assert "NoSuchBucket" in await response.get_data(as_text=True)
