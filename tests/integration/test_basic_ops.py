import pytest
import io
from app import create_app
from app.config import Config


@pytest.fixture(scope="function")
def client():
    app = create_app()
    app.testing = True
    with app.test_client() as client:
        yield client


def test_upload_download_presigned(client):
    """Upload a file, list it, and get a presigned download URL."""
    data = b"Hello, S3 compatible world!"
    file_like = io.BytesIO(data)

    # 1️⃣ Upload
    resp = client.post(
        f"/bucket/{Config.S3_BUCKET_NAME}/upload",
        data={"file": (file_like, "test.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302  # redirect after upload

    # 2️⃣ List objects
    resp = client.get("/")
    assert resp.status_code == 200
    assert "test.txt" in resp.get_data(as_text=True)

    # 3️⃣ Get presigned download URL
    dl_resp = client.get(f"/bucket/{Config.S3_BUCKET_NAME}/download/test.txt")
    assert dl_resp.status_code == 200
    json_data = dl_resp.get_json()
    assert "download_url" in json_data


def test_delete_file(client):
    """Upload a file, then delete it and verify it's gone."""
    data = b"Delete me!"
    file_like = io.BytesIO(data)

    # Upload
    resp = client.post(
        f"/bucket/{Config.S3_BUCKET_NAME}/upload",
        data={"file": (file_like, "to_delete.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302

    # Verify it's in the list
    resp = client.get("/")
    assert resp.status_code == 200
    assert "to_delete.txt" in resp.get_data(as_text=True)

    # Delete
    del_resp = client.post(
        f"/bucket/{Config.S3_BUCKET_NAME}/delete/to_delete.txt",
        follow_redirects=False,
    )
    assert del_resp.status_code in (302, 200)  # redirect or ok

    # Verify it's gone
    resp = client.get("/")
    assert resp.status_code == 200
    assert "to_delete.txt" not in resp.get_data(as_text=True)


def test_health_endpoint(client):
    """The /health endpoint should return 200 OK."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}