"""S3 backup helper, executed inside the API image by backup.mjs."""

import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    os.umask(0o077)
    action = sys.argv[1]
    root = Path("/backup")
    if urlparse(os.environ["S3_ENDPOINT_URL"]).hostname != "minio":
        raise RuntimeError("This local Compose tool requires the internal minio hostname")
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name="us-east-1",
    )
    bucket = os.environ["S3_BUCKET"]
    try:
        client.head_bucket(Bucket=bucket)
        exists = True
    except ClientError as error:
        if error.response["Error"]["Code"] not in {"404", "NoSuchBucket"}:
            raise
        exists = False

    if action == "empty":
        if exists and client.list_objects_v2(Bucket=bucket, MaxKeys=1).get("KeyCount", 0):
            raise RuntimeError("Restore requires an empty object bucket")
        return

    if action == "backup":
        records = []
        (root / "objects").mkdir()
        if exists:
            for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
                for entry in page.get("Contents", []):
                    key = entry["Key"]
                    filename = hashlib.sha256(key.encode()).hexdigest()
                    destination = root / "objects" / filename
                    metadata = client.head_object(Bucket=bucket, Key=key)
                    client.download_file(bucket, key, str(destination))
                    records.append(
                        {
                            "key": key,
                            "file": filename,
                            "sha256": digest(destination),
                            "size": destination.stat().st_size,
                            "content_type": metadata.get("ContentType"),
                            "metadata": metadata.get("Metadata", {}),
                        }
                    )
        (root / "objects.json").write_text(json.dumps(records, indent=2))
        return

    records = json.loads((root / "objects.json").read_text())
    # Validate all local bytes before making any restore writes.
    for record in records:
        filename = record["file"]
        if len(filename) != 64 or any(c not in "0123456789abcdef" for c in filename):
            raise RuntimeError("Unsafe object filename")
        source = root / "objects" / filename
        if source.is_symlink() or digest(source) != record["sha256"]:
            raise RuntimeError("Object checksum mismatch")
        if source.stat().st_size != record["size"]:
            raise RuntimeError("Object size mismatch")
    if action == "verify":
        return
    if action != "restore":
        raise RuntimeError("Unknown action")
    if exists and client.list_objects_v2(Bucket=bucket, MaxKeys=1).get("KeyCount", 0):
        raise RuntimeError("Restore requires an empty object bucket")
    if not exists:
        client.create_bucket(Bucket=bucket)
    for record in records:
        extra = {"Metadata": record["metadata"]}
        if record.get("content_type"):
            extra["ContentType"] = record["content_type"]
        client.upload_file(
            str(root / "objects" / record["file"]), bucket, record["key"], ExtraArgs=extra
        )


if __name__ == "__main__":
    main()
