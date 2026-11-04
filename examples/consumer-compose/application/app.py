import os
import boto3
from botocore.config import Config

endpoint = os.environ["S3_ENDPOINT_URL"]
bucket = os.environ["S3_BUCKET_NAME"]
s3 = boto3.client(
    "s3", endpoint_url=endpoint, region_name=os.environ["S3_REGION"],
    aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
    config=Config(s3={"addressing_style": "path"}),
)
s3.put_object(Bucket=bucket, Key="consumer.txt", Body=b"hello from consumer")
body = s3.get_object(Bucket=bucket, Key="consumer.txt")["Body"].read()
print(f"connected to {endpoint}; downloaded: {body.decode()}", flush=True)
