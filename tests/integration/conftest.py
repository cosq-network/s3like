import pytest
from moto import mock_aws
import boto3
from app import create_app
from app.config import Config


@pytest.fixture(scope="function")
def moto_s3():
    with mock_aws():
        # Create a fake bucket that the Flask app will use
        s3 = boto3.client(
            "s3",
            region_name=Config.S3_REGION,
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        s3.create_bucket(Bucket=Config.S3_BUCKET_NAME)
        yield   # test body runs here
        # bucket is automatically torn down after the yield


@pytest.fixture(scope="function")
def client(moto_s3):
    app = create_app()
    app.testing = True
    with app.test_client() as client:
        yield client