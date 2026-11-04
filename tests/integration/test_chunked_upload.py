import hashlib

import pytest
from app.config import Config

SIG = "chunk-signature=" + "a" * 64
STREAMING = "STREAMING-AWS4-HMAC-SHA256-PAYLOAD-TRAILER"


def framed(payload):
    body = f"{len(payload):x};{SIG}\r\n".encode() + payload + b"\r\n"
    body += f"0;{SIG}\r\n".encode()
    body += b"x-amz-checksum-crc32:kiJl9A==\r\nx-amz-trailer-signature:" + b"b" * 64 + b"\r\n\r\n"
    return body


def streaming_headers(payload, body):
    return {
        "x-amz-content-sha256": STREAMING,
        "Content-Encoding": "aws-chunked",
        "x-amz-decoded-content-length": str(len(payload)),
        "Content-Length": str(len(body)),
    }


@pytest.mark.asyncio
async def test_aws_chunked_put_stores_only_the_object_bytes(client):
    bucket = Config().S3_BUCKET_NAME
    payload = b"WorqNET authorized document download"
    body = framed(payload)

    put = await client.put(f"/{bucket}/chunked.txt", data=body, headers=streaming_headers(payload, body))
    assert put.status_code == 200
    assert put.headers["ETag"].strip('"') == hashlib.md5(payload).hexdigest()

    got = await client.get(f"/{bucket}/chunked.txt")
    assert got.status_code == 200
    assert await got.get_data() == payload
    assert got.headers["Content-Length"] == str(len(payload))
    # Only the object's own headers come back; the upload encoding is not stored with it.
    assert "aws-chunked" not in got.headers.get("Content-Encoding", "")


@pytest.mark.asyncio
async def test_aws_chunked_multipart_part(client):
    bucket = Config().S3_BUCKET_NAME
    created = await client.post(f"/{bucket}/parts.bin?uploads")
    assert created.status_code == 200
    upload_id = (await created.get_data(as_text=True)).split("<UploadId>")[1].split("</UploadId>")[0]

    payload = b"p" * 1000
    body = framed(payload)
    part = await client.put(f"/{bucket}/parts.bin?partNumber=1&uploadId={upload_id}", data=body,
                            headers=streaming_headers(payload, body))
    assert part.status_code == 200
    assert part.headers["ETag"].strip('"') == hashlib.md5(payload).hexdigest()


@pytest.mark.asyncio
async def test_plain_put_is_unchanged(client):
    bucket = Config().S3_BUCKET_NAME
    put = await client.put(f"/{bucket}/plain.txt", data=b"plain body")
    assert put.status_code == 200
    assert await (await client.get(f"/{bucket}/plain.txt")).get_data() == b"plain body"


@pytest.mark.asyncio
async def test_decoded_length_mismatch_is_refused_and_leaves_no_object(client):
    bucket = Config().S3_BUCKET_NAME
    payload = b"short"
    body = framed(payload)
    headers = streaming_headers(payload, body)
    headers["x-amz-decoded-content-length"] = "999"

    put = await client.put(f"/{bucket}/bad.txt", data=body, headers=headers)
    assert put.status_code == 400
    assert (await client.get(f"/{bucket}/bad.txt")).status_code == 404
