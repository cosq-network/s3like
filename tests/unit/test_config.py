from app.config import Config


def test_config_defaults():
    # No env vars set; should use defaults
    c = Config()
    assert c.SECRET_KEY == "super-secret-key-change-me"
    assert c.FLASK_ENV == "development"
    assert c.AWS_ACCESS_KEY_ID == "testkey"
    assert c.AWS_SECRET_ACCESS_KEY == "testsecret"
    assert c.S3_ENDPOINT_URL == "http://localhost:5555"
    assert c.S3_REGION == "us-east-1"
    assert c.S3_USE_SSL is False
    assert c.CONSOLE_USERNAME == ""
    assert c.CONSOLE_PASSWORD == ""