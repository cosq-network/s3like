from xml.etree import ElementTree
import pytest
from app.api.xml import response
from app.config import Config

@pytest.mark.asyncio
async def test_bucket_xml_uses_aws_shape():
    body = response("ListAllMyBucketsResult", {"Buckets": [{"Name": "one", "CreationDate": "now"}]})
    root = ElementTree.fromstring(await body.get_data())
    assert root.tag.endswith("ListAllMyBucketsResult")
    assert root.find("{*}Buckets/{*}Bucket/{*}Name").text == "one"

def test_config_aliases_and_invalid_values(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("S3_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("S3_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setenv("MINIO_ROOT_USER", "minio-user")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "minio-pass")
    monkeypatch.setenv("S3_MAX_OBJECT_SIZE", "bad")
    monkeypatch.setenv("S3_AUTO_CREATE_BUCKET", "off")
    c = Config()
    assert (c.S3_ACCESS_KEY_ID, c.S3_SECRET_ACCESS_KEY) == ("minio-user", "minio-pass")
    assert c.S3_MAX_OBJECT_SIZE == 5 * 1024 * 1024 * 1024 and c.S3_AUTO_CREATE_BUCKET is False

def test_production_rejects_dev_credentials(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("S3_DEVELOPMENT_MODE", "false")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "dev-access")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "dev-secret")
    from app import create_s3_app
    import pytest
    with pytest.raises(RuntimeError, match="Default credentials"):
        create_s3_app()
