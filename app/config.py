import os

class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-me")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    # S3 – all overridable via environment variables
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "testkey")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "testsecret")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://localhost:5555")
    S3_REGION = os.getenv("S3_REGION", "us-east-1")
    S3_USE_SSL = os.getenv("S3_USE_SSL", "False").lower() in ("true", "1", "yes")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "my-bucket")

    # Optional Basic Auth for the console
    CONSOLE_USERNAME = os.getenv("CONSOLE_USERNAME", "")
    CONSOLE_PASSWORD = os.getenv("CONSOLE_PASSWORD", "")