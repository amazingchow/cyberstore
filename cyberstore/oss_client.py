"""Boto3 wrapper for Aliyun OSS operations via S3-compatible API."""

from __future__ import annotations

import os
from typing import Any, Callable

import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from cyberstore.config import AppConfig
from cyberstore.r2_client import (
    ListObjectsResult,
    R2Bucket,
    R2ConnectionError,
    R2Error,
    R2Object,
    R2PermissionError,
    R2SizeLimitError,
)
from cyberstore.utils import MAX_OBJECT_SIZE

_BOTO_CONFIG = BotocoreConfig(
    connect_timeout=10,
    read_timeout=15,
    retries={"max_attempts": 1},
    s3={"addressing_style": "virtual", "payload_signing_enabled": False},
    request_checksum_calculation="when_required",
    response_checksum_validation="when_required",
)

ProgressCallback = Callable[[int], None]

OSSError = R2Error
OSSConnectionError = R2ConnectionError
OSSPermissionError = R2PermissionError
OSSSizeLimitError = R2SizeLimitError


class OSSClient:
    """Wrapper around boto3 for Aliyun OSS operations via S3-compatible API."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            oss = self._config.oss
            endpoint = oss.endpoint.rstrip("/")
            if not endpoint.startswith("http"):
                endpoint = f"https://{endpoint}"
            self._client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=oss.access_key_id,
                aws_secret_access_key=oss.access_key_secret,
                region_name=oss.region_name(),
                config=_BOTO_CONFIG,
            )
        return self._client

    def reset_client(self) -> None:
        self._client = None

    def test_connection(self) -> bool:
        """Test the OSS connection by listing buckets."""
        success, _ = self.test_connection_detail()
        return success

    def test_connection_detail(self) -> tuple[bool, str]:
        """Test the OSS connection, returning (success, message)."""
        try:
            bucket = self._config.oss.bucket
            self._get_client().list_objects_v2(Bucket=bucket, MaxKeys=1)
            return True, "Connected successfully"
        except NoCredentialsError as e:
            return False, f"Invalid credentials: {e}"
        except EndpointConnectionError as e:
            return False, f"Cannot reach endpoint: {e}"
        except ClientError as e:
            return False, f"API error: {e}"
        except Exception as e:
            return False, f"Unexpected error: {type(e).__name__}: {e}"

    def list_buckets(self) -> list[R2Bucket]:
        """List all OSS buckets."""
        try:
            response = self._get_client().list_buckets()
            return [
                R2Bucket(
                    name=b["Name"],
                    creation_date=b.get("CreationDate"),
                )
                for b in response.get("Buckets", [])
            ]
        except ClientError as e:
            raise R2PermissionError(f"Failed to list buckets: {e}") from e
        except EndpointConnectionError as e:
            raise R2ConnectionError(f"Connection failed: {e}") from e

    def list_objects(self, bucket: str, prefix: str = "", delimiter: str = "/") -> ListObjectsResult:
        """List objects in a bucket with optional prefix and delimiter."""
        try:
            kwargs: dict[str, Any] = {
                "Bucket": bucket,
                "Prefix": prefix,
                "Delimiter": delimiter,
                "MaxKeys": 1000,
            }
            result = ListObjectsResult(prefix=prefix)
            while True:
                response = self._get_client().list_objects_v2(**kwargs)

                for cp in response.get("CommonPrefixes", []):
                    result.folders.append(R2Object(key=cp["Prefix"], is_folder=True))

                for obj in response.get("Contents", []):
                    if obj["Key"] == prefix:
                        continue
                    result.objects.append(
                        R2Object(
                            key=obj["Key"],
                            size=obj.get("Size", 0),
                            last_modified=obj.get("LastModified"),
                            etag=obj.get("ETag", "").strip('"'),
                        )
                    )

                if response.get("IsTruncated"):
                    kwargs["ContinuationToken"] = response["NextContinuationToken"]
                else:
                    break

            return result
        except ClientError as e:
            raise R2PermissionError(f"Failed to list objects: {e}") from e
        except EndpointConnectionError as e:
            raise R2ConnectionError(f"Connection failed: {e}") from e

    def head_object(self, bucket: str, key: str) -> dict[str, Any]:
        """Get object metadata."""
        try:
            response = self._get_client().head_object(Bucket=bucket, Key=key)
            return {
                "key": key,
                "size": response.get("ContentLength", 0),
                "content_type": response.get("ContentType", ""),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag", "").strip('"'),
                "metadata": response.get("Metadata", {}),
            }
        except ClientError as e:
            raise OSSError(f"Failed to get object info: {e}") from e

    def upload_file(
        self,
        bucket: str,
        local_path: str,
        key: str,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Upload a file to OSS with size validation and progress reporting."""
        import mimetypes

        file_size = os.path.getsize(local_path)
        if file_size > MAX_OBJECT_SIZE:
            raise OSSSizeLimitError(f"File size ({file_size:,} bytes) exceeds 10 MB limit")

        try:
            mime_type, _ = mimetypes.guess_type(local_path)
            content_type = mime_type or "application/octet-stream"

            with open(local_path, "rb") as f:
                body = f.read()

            self._get_client().put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )

            if progress_callback and file_size > 0:
                progress_callback(file_size)

        except ClientError as e:
            raise OSSError(f"Upload failed: {e}") from e

    def download_file(
        self,
        bucket: str,
        key: str,
        local_path: str,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Download a file from OSS with progress reporting."""
        try:
            self._get_client().download_file(
                bucket,
                key,
                local_path,
                Callback=progress_callback,
            )
        except ClientError as e:
            raise OSSError(f"Download failed: {e}") from e

    def delete_object(self, bucket: str, key: str) -> None:
        """Delete a single object."""
        try:
            self._get_client().delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            raise OSSError(f"Delete failed: {e}") from e

    def delete_objects(self, bucket: str, keys: list[str]) -> None:
        """Delete multiple objects one by one.

        OSS's S3-compatible DeleteObjects requires a Content-MD5 header that
        newer boto3 no longer sends automatically, so we use individual deletes
        to avoid the compatibility issue.
        """
        if not keys:
            return
        try:
            for key in keys:
                self._get_client().delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            raise OSSError(f"Bulk delete failed: {e}") from e

    def create_bucket(self, name: str) -> None:
        """Create a new OSS bucket."""
        try:
            region = self._config.oss.region_name()
            self._get_client().create_bucket(
                Bucket=name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        except ClientError as e:
            raise OSSError(f"Failed to create bucket: {e}") from e

    def delete_bucket(self, name: str) -> None:
        """Delete an empty OSS bucket."""
        try:
            self._get_client().delete_bucket(Bucket=name)
        except ClientError as e:
            raise OSSError(f"Failed to delete bucket: {e}") from e

    def generate_presigned_url(self, bucket: str, key: str, expiry: int | None = None) -> str:
        """Generate a presigned URL for an OSS object."""
        if expiry is None:
            expiry = self._config.preferences.presigned_expiry
        try:
            return self._get_client().generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expiry,
            )
        except ClientError as e:
            raise OSSError(f"Failed to generate presigned URL: {e}") from e

    def get_cdn_url(self, bucket: str, key: str) -> str | None:
        """Construct a CDN URL for an object using configured domain."""
        base_url = self._config.cdn.get_base_url()
        if base_url is None:
            return None
        return f"{base_url}/{key}"
