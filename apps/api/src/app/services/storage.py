from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import Settings


class ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=str(settings.s3_endpoint_url),
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            region_name="us-east-1",
            config=Config(s3={"addressing_style": "path"}),
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def upload_file(self, source: Path, key: str, content_type: str) -> None:
        self.ensure_bucket()
        self._client.upload_file(
            str(source), self._bucket, key, ExtraArgs={"ContentType": content_type}
        )

    def download_file(self, key: str, destination: Path) -> None:
        self._client.download_file(self._bucket, key, str(destination))

    def copy(self, source_key: str, destination_key: str) -> None:
        self._client.copy_object(
            Bucket=self._bucket,
            Key=destination_key,
            CopySource={"Bucket": self._bucket, "Key": source_key},
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
