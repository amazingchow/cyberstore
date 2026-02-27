"""Boto3 wrapper for all Cloudflare R2 operations."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from cyberstore.config import AppConfig
from cyberstore.utils import MAX_OBJECT_SIZE

_BOTO_CONFIG = BotocoreConfig(
    connect_timeout=10,
    read_timeout=15,
    retries={"max_attempts": 1},
)

ProgressCallback = Callable[[int], None]


@dataclass
class R2Object:
    """Represents an object in R2 storage."""

    key: str
    size: int = 0
    last_modified: Any = None
    etag: str = ""
    content_type: str = ""
    is_folder: bool = False

    @property
    def name(self) -> str:
        if self.is_folder:
            parts = self.key.rstrip("/").split("/")
            return parts[-1] + "/"
        return self.key.split("/")[-1]


@dataclass
class R2Bucket:
    """Represents an R2 bucket."""

    name: str
    creation_date: Any = None


@dataclass
class ListObjectsResult:
    """Result from listing objects in a bucket."""

    objects: list[R2Object] = field(default_factory=list)
    folders: list[R2Object] = field(default_factory=list)
    prefix: str = ""


class R2Error(Exception):
    """Base exception for R2 operations."""


class R2ConnectionError(R2Error):
    """Connection error."""


class R2PermissionError(R2Error):
    """Permission/credential error."""


class R2SizeLimitError(R2Error):
    """File exceeds size limit."""


class R2Client:
    """Wrapper around boto3 for Cloudflare R2 operations."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self._config.r2.endpoint_url,
                aws_access_key_id=self._config.r2.access_key_id,
                aws_secret_access_key=self._config.r2.secret_access_key,
                region_name="auto",
                config=_BOTO_CONFIG,
            )
        return self._client

    def reset_client(self) -> None:
        self._client = None

    def test_connection(self) -> bool:
        """Test the R2 connection by listing buckets."""
        success, _ = self.test_connection_detail()
        return success

    def test_connection_detail(self) -> tuple[bool, str]:
        """Test the R2 connection, returning (success, message)."""
        try:
            self._get_client().list_buckets()
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
        """List all buckets."""
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
            raise R2Error(f"Failed to get object info: {e}") from e

    def upload_file(
        self,
        bucket: str,
        local_path: str,
        key: str,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Upload a file to R2 with size validation and progress reporting."""
        file_size = os.path.getsize(local_path)
        if file_size > MAX_OBJECT_SIZE:
            raise R2SizeLimitError(f"File size ({file_size:,} bytes) exceeds 10 MB limit")

        try:
            extra_args: dict[str, str] = {}
            import mimetypes

            mime_type, _ = mimetypes.guess_type(local_path)
            if mime_type:
                extra_args["ContentType"] = mime_type

            callback = None
            if progress_callback:
                callback = progress_callback

            self._get_client().upload_file(
                local_path,
                bucket,
                key,
                ExtraArgs=extra_args if extra_args else None,
                Callback=callback,
            )
        except ClientError as e:
            raise R2Error(f"Upload failed: {e}") from e

    def download_file(
        self,
        bucket: str,
        key: str,
        local_path: str,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Download a file from R2 with progress reporting."""
        try:
            callback = None
            if progress_callback:
                callback = progress_callback

            self._get_client().download_file(
                bucket,
                key,
                local_path,
                Callback=callback,
            )
        except ClientError as e:
            raise R2Error(f"Download failed: {e}") from e

    def delete_object(self, bucket: str, key: str) -> None:
        """Delete a single object."""
        try:
            self._get_client().delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            raise R2Error(f"Delete failed: {e}") from e

    def delete_objects(self, bucket: str, keys: list[str]) -> None:
        """Delete multiple objects."""
        if not keys:
            return
        try:
            objects = [{"Key": k} for k in keys]
            self._get_client().delete_objects(Bucket=bucket, Delete={"Objects": objects})
        except ClientError as e:
            raise R2Error(f"Bulk delete failed: {e}") from e

    def create_bucket(self, name: str) -> None:
        """Create a new bucket."""
        try:
            self._get_client().create_bucket(Bucket=name)
        except ClientError as e:
            raise R2Error(f"Failed to create bucket: {e}") from e

    def delete_bucket(self, name: str) -> None:
        """Delete an empty bucket."""
        try:
            self._get_client().delete_bucket(Bucket=name)
        except ClientError as e:
            raise R2Error(f"Failed to delete bucket: {e}") from e

    def generate_presigned_url(self, bucket: str, key: str, expiry: int | None = None) -> str:
        """Generate a presigned URL for an object."""
        if expiry is None:
            expiry = self._config.preferences.presigned_expiry
        try:
            return self._get_client().generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expiry,
            )
        except ClientError as e:
            raise R2Error(f"Failed to generate presigned URL: {e}") from e

    def get_cdn_url(self, bucket: str, key: str) -> str | None:
        """Construct a CDN URL for an object using configured domain."""
        base_url = self._config.cdn.get_base_url()
        if base_url is None:
            return None
        return f"{base_url}/{key}"
