import base64
import io
import pytest
from app import create_console_app
from werkzeug.datastructures import FileStorage

@pytest.fixture
def console_app(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("S3_BUCKET_NAME", "console-bucket")
    monkeypatch.setenv("CONSOLE_USERNAME", "admin")
    monkeypatch.setenv("CONSOLE_PASSWORD", "secret")
    app = create_console_app()
    app.testing = True
    return app

@pytest.mark.asyncio
async def test_console_basic_auth_and_object_flow(console_app):
    auth = {"Authorization": "Basic " + base64.b64encode(b"admin:secret").decode()}
    async with console_app.test_app():
        async with console_app.test_client() as client:
            denied = await client.get("/")
            assert denied.status_code == 401 and "WWW-Authenticate" in denied.headers
            assert (await client.get("/", headers=auth)).status_code == 200
            assert (await client.post("/bucket/create", headers=auth, form={"name": "new-bucket"})).status_code == 302
            uploaded = await client.post("/bucket/new-bucket/upload", headers=auth, files={"file": FileStorage(stream=io.BytesIO(b"console"), filename="a.txt")})
            assert uploaded.status_code == 302
            page = await client.get("/bucket/new-bucket", headers=auth)
            assert page.status_code == 200 and "a.txt" in await page.get_data(as_text=True)
            downloaded = await client.get("/bucket/new-bucket/download/a.txt", headers=auth)
            assert downloaded.status_code == 200 and await downloaded.get_data() == b"console"
