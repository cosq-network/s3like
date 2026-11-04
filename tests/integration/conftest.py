import pytest
import shutil
from pathlib import Path
from uuid import uuid4
from app import create_app

@pytest.fixture
def app(monkeypatch):
    data_dir = Path.cwd() / ".test-data" / uuid4().hex
    data_dir.mkdir(parents=True)
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("S3_BUCKET_NAME", "dev-bucket")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
    application = create_app()
    monkeypatch.setattr("app.api.service.validate_with_error", lambda: (True, None))
    application.testing = True
    try:
        yield application
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

@pytest.fixture
async def client(app):
    async with app.test_app():
        async with app.test_client() as test_client:
            yield test_client
