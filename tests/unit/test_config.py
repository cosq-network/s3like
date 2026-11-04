import pytest
from app.config import Config


def test_config_defaults():
    """Config should use environment variable defaults."""
    c = Config()
    assert c.SECRET_KEY == "super-secret-key-change-me"
    assert c.FLASK_ENV == "development"
    assert c.S3_ACCESS_KEY_ID == "dev-access"
    assert c.S3_SECRET_ACCESS_KEY == "dev-secret"
    assert c.S3_ENDPOINT_URL == "http://localhost:9000"
    assert c.S3_REGION == "us-east-1"
    assert c.S3_BUCKET_NAME == "dev-bucket"
    assert c.CONSOLE_USERNAME == ""
    assert c.CONSOLE_PASSWORD == ""
