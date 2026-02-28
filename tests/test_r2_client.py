"""Integration tests for R2Client against a real Cloudflare R2 instance.

Configuration is read from ~/.config/cyberstore/config.toml.
All tests are skipped when:
  - The config file does not exist
  - storage_provider is not 'r2'
  - R2 config is incomplete (missing account_id, access_key_id, or secret_access_key)
  - R2_TEST_BUCKET environment variable is not set

To run:
    R2_TEST_BUCKET=<your-bucket> pytest tests/test_r2_client.py -v
"""

from __future__ import annotations

import os
import tempfile

import pytest

from cyberstore.config import CONFIG_FILE, PROVIDER_R2, AppConfig
from cyberstore.r2_client import (
    ListObjectsResult,
    R2Bucket,
    R2Client,
    R2Error,
    R2Object,
    R2SizeLimitError,
)
from cyberstore.utils import MAX_OBJECT_SIZE

# ── skip guard ────────────────────────────────────────────────────────────────

_skip_reason: str | None = None

if not CONFIG_FILE.exists():
    _skip_reason = (
        f"Config file not found: {CONFIG_FILE}\n"
        "Create it by running `cyberstore` and completing the R2 setup, "
        "or write it manually:\n\n"
        "    [general]\n"
        "    storage_provider = 'r2'\n\n"
        "    [r2]\n"
        "    account_id        = '<AccountId>'\n"
        "    access_key_id     = '<AccessKeyId>'\n"
        "    secret_access_key = '<SecretAccessKey>'\n"
    )
else:
    _cfg = AppConfig.load()
    if _cfg.storage_provider != PROVIDER_R2:
        _skip_reason = f"storage_provider = '{_cfg.storage_provider}' in {CONFIG_FILE}. Set it to 'r2' to run R2 tests."
    elif not _cfg.r2.is_valid():
        missing = [f for f in ("account_id", "access_key_id", "secret_access_key") if not getattr(_cfg.r2, f)]
        _skip_reason = f"R2 config incomplete — missing fields: {', '.join(missing)}"
    elif not os.environ.get("R2_TEST_BUCKET"):
        _skip_reason = (
            "R2_TEST_BUCKET environment variable not set.\n"
            "Run with:  R2_TEST_BUCKET=<your-bucket> pytest tests/test_r2_client.py"
        )

pytestmark = pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")

# Prefix for all objects created during tests — makes cleanup easy and avoids
# collisions with real data.
_TEST_PREFIX = "_cyberstore_test_/"


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def cfg() -> AppConfig:
    return AppConfig.load()


@pytest.fixture(scope="module")
def client(cfg: AppConfig) -> R2Client:
    return R2Client(cfg)


@pytest.fixture(scope="module")
def bucket() -> str:
    return os.environ["R2_TEST_BUCKET"]


# ── helpers ───────────────────────────────────────────────────────────────────


def _tmp_file(content: bytes, suffix: str = ".txt") -> str:
    """Write content to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, content)
    os.close(fd)
    return path


def _upload_and_cleanup(client: R2Client, bucket: str, key: str, content: bytes) -> None:
    """Upload a temp file then remove the local copy."""
    path = _tmp_file(content)
    try:
        client.upload_file(bucket, path, key)
    finally:
        os.unlink(path)


# ── connection ────────────────────────────────────────────────────────────────


class TestConnection:
    def test_connection_succeeds(self, client: R2Client):
        assert client.test_connection() is True

    def test_connection_detail_returns_true_and_message(self, client: R2Client):
        ok, msg = client.test_connection_detail()
        assert ok is True
        assert isinstance(msg, str) and msg

    def test_wrong_credentials_returns_false(self, cfg: AppConfig):
        from cyberstore.config import R2Config

        bad = AppConfig()
        bad.storage_provider = PROVIDER_R2
        bad.r2 = R2Config(
            account_id=cfg.r2.account_id,
            access_key_id="INVALID_KEY_ID_00000000000000000000",
            secret_access_key="INVALID_SECRET_0000000000000000000000000000",
        )
        ok, msg = R2Client(bad).test_connection_detail()
        assert ok is False
        assert msg

    def test_reset_client_forces_reconnect(self, client: R2Client):
        """reset_client() clears cached boto3 client; subsequent calls should still succeed."""
        assert client.test_connection() is True
        client.reset_client()
        assert client.test_connection() is True


# ── list_buckets ──────────────────────────────────────────────────────────────


class TestListBuckets:
    def test_list_buckets_returns_list(self, client: R2Client):
        buckets = client.list_buckets()
        assert isinstance(buckets, list)

    def test_list_buckets_items_are_r2bucket(self, client: R2Client):
        buckets = client.list_buckets()
        for b in buckets:
            assert isinstance(b, R2Bucket)
            assert isinstance(b.name, str) and b.name

    def test_list_buckets_contains_test_bucket(self, client: R2Client, bucket: str):
        buckets = client.list_buckets()
        names = {b.name for b in buckets}
        assert bucket in names

    def test_list_buckets_creation_date_field(self, client: R2Client):
        buckets = client.list_buckets()
        # creation_date may be None for some providers but the attribute must exist
        for b in buckets:
            assert hasattr(b, "creation_date")


# ── upload ────────────────────────────────────────────────────────────────────


class TestUpload:
    def test_upload_text_file(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "upload_text.txt"
        path = _tmp_file(b"hello r2")
        try:
            client.upload_file(bucket, path, key)
            meta = client.head_object(bucket, key)
            assert meta["size"] == len(b"hello r2")
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)

    def test_upload_binary_file(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "upload_binary.bin"
        content = bytes(range(256))
        path = _tmp_file(content, suffix=".bin")
        try:
            client.upload_file(bucket, path, key)
            meta = client.head_object(bucket, key)
            assert meta["size"] == 256
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)

    def test_upload_zero_byte_file(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "upload_empty.txt"
        path = _tmp_file(b"")
        try:
            client.upload_file(bucket, path, key)
            meta = client.head_object(bucket, key)
            assert meta["size"] == 0
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)

    def test_upload_sets_content_type_for_known_extension(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "upload_image.png"
        # Minimal valid 1×1 PNG
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        path = _tmp_file(png, suffix=".png")
        try:
            client.upload_file(bucket, path, key)
            meta = client.head_object(bucket, key)
            assert "image" in meta["content_type"]
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)

    def test_upload_overwrites_existing_object(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "upload_overwrite.txt"
        path_v1 = _tmp_file(b"version one")
        path_v2 = _tmp_file(b"version two -- longer")
        try:
            client.upload_file(bucket, path_v1, key)
            client.upload_file(bucket, path_v2, key)
            meta = client.head_object(bucket, key)
            assert meta["size"] == len(b"version two -- longer")
        finally:
            os.unlink(path_v1)
            os.unlink(path_v2)
            client.delete_object(bucket, key)

    def test_upload_progress_callback_called(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "upload_progress.txt"
        content = b"progress callback test"
        path = _tmp_file(content)
        reported: list[int] = []
        try:
            client.upload_file(bucket, path, key, progress_callback=reported.append)
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)
        assert reported
        assert sum(reported) == len(content)

    def test_upload_progress_callback_none_does_not_raise(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "upload_no_cb.txt"
        path = _tmp_file(b"no callback")
        try:
            client.upload_file(bucket, path, key, progress_callback=None)
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)

    def test_upload_size_limit_raises(self, client: R2Client, bucket: str):
        path = _tmp_file(b"x" * (MAX_OBJECT_SIZE + 1))
        try:
            with pytest.raises(R2SizeLimitError):
                client.upload_file(bucket, path, _TEST_PREFIX + "too_large.bin")
        finally:
            os.unlink(path)

    def test_upload_key_with_nested_path(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "a/b/c/nested.txt"
        path = _tmp_file(b"nested path")
        try:
            client.upload_file(bucket, path, key)
            meta = client.head_object(bucket, key)
            assert meta["key"] == key
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)


# ── download ──────────────────────────────────────────────────────────────────


class TestDownload:
    def test_download_matches_uploaded_content(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "download_verify.txt"
        content = b"download verification content"
        path = _tmp_file(content)
        client.upload_file(bucket, path, key)
        os.unlink(path)

        fd, local = tempfile.mkstemp()
        os.close(fd)
        try:
            client.download_file(bucket, key, local)
            with open(local, "rb") as f:
                assert f.read() == content
        finally:
            os.unlink(local)
            client.delete_object(bucket, key)

    def test_download_binary_file(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "download_binary.bin"
        content = bytes(range(256)) * 10
        path = _tmp_file(content, suffix=".bin")
        client.upload_file(bucket, path, key)
        os.unlink(path)

        fd, local = tempfile.mkstemp(suffix=".bin")
        os.close(fd)
        try:
            client.download_file(bucket, key, local)
            with open(local, "rb") as f:
                assert f.read() == content
        finally:
            os.unlink(local)
            client.delete_object(bucket, key)

    def test_download_progress_callback_called(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "download_progress.txt"
        content = b"download progress test " * 100
        path = _tmp_file(content)
        client.upload_file(bucket, path, key)
        os.unlink(path)

        reported: list[int] = []
        fd, local = tempfile.mkstemp()
        os.close(fd)
        try:
            client.download_file(bucket, key, local, progress_callback=reported.append)
        finally:
            os.unlink(local)
            client.delete_object(bucket, key)
        assert sum(reported) == len(content)

    def test_download_nonexistent_key_raises(self, client: R2Client, bucket: str):
        fd, local = tempfile.mkstemp()
        os.close(fd)
        try:
            with pytest.raises(R2Error):
                client.download_file(bucket, "_nonexistent_xyz_/missing.txt", local)
        finally:
            os.unlink(local)

    def test_download_overwrites_existing_local_file(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "download_overwrite.txt"
        content = b"overwrite local file"
        path = _tmp_file(content)
        client.upload_file(bucket, path, key)
        os.unlink(path)

        fd, local = tempfile.mkstemp()
        os.write(fd, b"old local content that should be replaced")
        os.close(fd)
        try:
            client.download_file(bucket, key, local)
            with open(local, "rb") as f:
                assert f.read() == content
        finally:
            os.unlink(local)
            client.delete_object(bucket, key)


# ── head_object ───────────────────────────────────────────────────────────────


class TestHeadObject:
    def test_head_returns_expected_fields(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "head_fields.txt"
        content = b"head object fields test"
        _upload_and_cleanup(client, bucket, key, content)
        try:
            meta = client.head_object(bucket, key)
            assert meta["key"] == key
            assert meta["size"] == len(content)
            assert meta["content_type"]
            assert meta["last_modified"] is not None
            assert meta["etag"]
            assert isinstance(meta["metadata"], dict)
        finally:
            client.delete_object(bucket, key)

    def test_head_nonexistent_key_raises(self, client: R2Client, bucket: str):
        with pytest.raises(R2Error):
            client.head_object(bucket, "_nonexistent_xyz_/no_such_file.txt")

    def test_head_size_matches_content(self, client: R2Client, bucket: str):
        for size in (0, 1, 1024, 8192):
            key = _TEST_PREFIX + f"head_size_{size}.bin"
            content = b"a" * size
            _upload_and_cleanup(client, bucket, key, content)
            try:
                assert client.head_object(bucket, key)["size"] == size
            finally:
                client.delete_object(bucket, key)

    def test_head_etag_is_non_empty_string(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "head_etag.txt"
        _upload_and_cleanup(client, bucket, key, b"etag check")
        try:
            meta = client.head_object(bucket, key)
            assert isinstance(meta["etag"], str) and meta["etag"]
            # boto3 strips surrounding quotes; make sure we don't have leftover quotes
            assert not meta["etag"].startswith('"')
            assert not meta["etag"].endswith('"')
        finally:
            client.delete_object(bucket, key)


# ── list_objects ──────────────────────────────────────────────────────────────


class TestListObjects:
    def test_list_returns_result_object(self, client: R2Client, bucket: str):
        result = client.list_objects(bucket, prefix="")
        assert isinstance(result, ListObjectsResult)
        assert hasattr(result, "objects")
        assert hasattr(result, "folders")
        assert isinstance(result.objects, list)
        assert isinstance(result.folders, list)

    def test_list_finds_uploaded_file(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "list_find/item.txt"
        _upload_and_cleanup(client, bucket, key, b"list find")
        try:
            result = client.list_objects(bucket, prefix=_TEST_PREFIX + "list_find/")
            assert any(o.key == key for o in result.objects)
        finally:
            client.delete_object(bucket, key)

    def test_list_with_prefix_shows_subfolder(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "list_folder/sub/file.txt"
        _upload_and_cleanup(client, bucket, key, b"subfolder")
        try:
            result = client.list_objects(bucket, prefix=_TEST_PREFIX + "list_folder/")
            folder_keys = [f.key for f in result.folders]
            assert any("sub" in k for k in folder_keys)
        finally:
            client.delete_object(bucket, key)

    def test_list_nonexistent_prefix_returns_empty(self, client: R2Client, bucket: str):
        result = client.list_objects(bucket, prefix="_nonexistent_prefix_xyz_/")
        assert result.objects == []
        assert result.folders == []

    def test_list_folder_objects_have_is_folder_flag(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "list_flag/nested/deep.txt"
        _upload_and_cleanup(client, bucket, key, b"flag")
        try:
            result = client.list_objects(bucket, prefix=_TEST_PREFIX + "list_flag/")
            assert all(f.is_folder for f in result.folders)
            assert all(not o.is_folder for o in result.objects)
        finally:
            client.delete_object(bucket, key)

    def test_list_multiple_files_under_prefix(self, client: R2Client, bucket: str):
        prefix = _TEST_PREFIX + "list_multi/"
        keys = [prefix + f"file_{i}.txt" for i in range(5)]
        paths = [_tmp_file(f"content {i}".encode()) for i in range(5)]
        for path, key in zip(paths, keys):
            client.upload_file(bucket, path, key)
            os.unlink(path)
        try:
            result = client.list_objects(bucket, prefix=prefix)
            found = {o.key for o in result.objects}
            assert set(keys).issubset(found)
        finally:
            client.delete_objects(bucket, keys)

    def test_list_result_prefix_field_matches_input(self, client: R2Client, bucket: str):
        prefix = _TEST_PREFIX + "list_prefix_field/"
        result = client.list_objects(bucket, prefix=prefix)
        assert result.prefix == prefix

    def test_list_prefix_key_not_included_as_object(self, client: R2Client, bucket: str):
        """A key that exactly equals the prefix should be filtered out of objects."""
        prefix = _TEST_PREFIX + "list_self/"
        # Upload an object whose key is exactly the prefix string
        exact_key = prefix  # e.g. "_cyberstore_test_/list_self/"
        path = _tmp_file(b"exact match")
        try:
            client.upload_file(bucket, path, exact_key)
            result = client.list_objects(bucket, prefix=prefix)
            assert not any(o.key == exact_key for o in result.objects)
        finally:
            os.unlink(path)
            client.delete_object(bucket, exact_key)


# ── delete ────────────────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_object_removes_it(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "delete_single.txt"
        _upload_and_cleanup(client, bucket, key, b"to be deleted")
        client.delete_object(bucket, key)
        with pytest.raises(R2Error):
            client.head_object(bucket, key)

    def test_delete_nonexistent_object_does_not_raise(self, client: R2Client, bucket: str):
        # S3/R2 delete is idempotent
        client.delete_object(bucket, "_nonexistent_xyz_/ghost.txt")

    def test_delete_objects_bulk(self, client: R2Client, bucket: str):
        keys = [_TEST_PREFIX + f"bulk_del_{i}.txt" for i in range(4)]
        paths = [_tmp_file(f"bulk {i}".encode()) for i in range(4)]
        for path, key in zip(paths, keys):
            client.upload_file(bucket, path, key)
            os.unlink(path)
        client.delete_objects(bucket, keys)
        for key in keys:
            with pytest.raises(R2Error):
                client.head_object(bucket, key)

    def test_delete_objects_empty_list_does_not_raise(self, client: R2Client, bucket: str):
        client.delete_objects(bucket, [])

    def test_delete_objects_partial_nonexistent_does_not_raise(self, client: R2Client, bucket: str):
        key_real = _TEST_PREFIX + "partial_del_real.txt"
        key_ghost = _TEST_PREFIX + "partial_del_ghost_xyz.txt"
        _upload_and_cleanup(client, bucket, key_real, b"real")
        # ghost key was never uploaded — bulk delete must still succeed
        client.delete_objects(bucket, [key_real, key_ghost])
        with pytest.raises(R2Error):
            client.head_object(bucket, key_real)


# ── presigned url ─────────────────────────────────────────────────────────────


class TestPresignedUrl:
    def test_presigned_url_is_valid_http_url(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "presign.txt"
        _upload_and_cleanup(client, bucket, key, b"presign content")
        try:
            url = client.generate_presigned_url(bucket, key)
            assert url.startswith("http")
            assert key in url or bucket in url
        finally:
            client.delete_object(bucket, key)

    def test_presigned_url_custom_expiry(self, client: R2Client, bucket: str):
        key = _TEST_PREFIX + "presign_expiry.txt"
        _upload_and_cleanup(client, bucket, key, b"expiry test")
        try:
            url = client.generate_presigned_url(bucket, key, expiry=300)
            assert url.startswith("http")
        finally:
            client.delete_object(bucket, key)

    def test_presigned_url_default_expiry_uses_config(self, client: R2Client, bucket: str, cfg: AppConfig):
        key = _TEST_PREFIX + "presign_default_expiry.txt"
        _upload_and_cleanup(client, bucket, key, b"default expiry")
        try:
            url = client.generate_presigned_url(bucket, key)
            assert url.startswith("http")
            # Expiry value from config should appear somewhere in the signed URL
            assert str(cfg.preferences.presigned_expiry) in url
        finally:
            client.delete_object(bucket, key)

    def test_presigned_url_accessible_via_http(self, client: R2Client, bucket: str, cfg: AppConfig):
        """Verify that the presigned URL returns HTTP 200 and correct content.

        Skipped when neither a custom domain nor an r2.dev subdomain is configured,
        because the default R2 endpoint requires the account to have public access
        enabled, which is off by default.
        """
        if not cfg.cdn.custom_domain and not cfg.cdn.r2_dev_subdomain:
            pytest.skip("No public CDN domain configured — cannot verify presigned URL via HTTP")

        import urllib.request

        key = _TEST_PREFIX + "presign_fetch.txt"
        content = b"presigned fetch test"
        _upload_and_cleanup(client, bucket, key, content)
        try:
            url = client.generate_presigned_url(bucket, key, expiry=60)
            with urllib.request.urlopen(url) as resp:
                assert resp.status == 200
                assert resp.read() == content
        finally:
            client.delete_object(bucket, key)


# ── cdn url ───────────────────────────────────────────────────────────────────


class TestCdnUrl:
    def test_cdn_url_none_when_no_cdn_configured(self, client: R2Client, bucket: str, cfg: AppConfig):
        if cfg.cdn.custom_domain or cfg.cdn.r2_dev_subdomain:
            pytest.skip("CDN domain is configured — skipping 'no CDN' test")
        assert client.get_cdn_url(bucket, "some/key.txt") is None

    def test_cdn_url_uses_custom_domain(self, client: R2Client, bucket: str, cfg: AppConfig):
        if not cfg.cdn.custom_domain:
            pytest.skip("No custom CDN domain configured")
        url = client.get_cdn_url(bucket, "path/to/file.png")
        assert url is not None
        assert "file.png" in url
        assert url.startswith("http")

    def test_cdn_url_uses_r2_dev_subdomain(self, client: R2Client, bucket: str, cfg: AppConfig):
        if cfg.cdn.custom_domain:
            pytest.skip("custom_domain takes priority over r2_dev_subdomain — skipping r2.dev test")
        if not cfg.cdn.r2_dev_subdomain:
            pytest.skip("No r2.dev subdomain configured")
        url = client.get_cdn_url(bucket, "path/to/asset.js")
        assert url is not None
        assert "asset.js" in url
        assert url.startswith("http")

    def test_cdn_url_key_appended_correctly(self, client: R2Client, bucket: str, cfg: AppConfig):
        if not cfg.cdn.custom_domain and not cfg.cdn.r2_dev_subdomain:
            pytest.skip("No CDN domain configured")
        key = "folder/sub/file.txt"
        url = client.get_cdn_url(bucket, key)
        assert url is not None
        assert url.endswith(key)

    def test_cdn_url_no_double_slash(self, client: R2Client, bucket: str, cfg: AppConfig):
        if not cfg.cdn.custom_domain and not cfg.cdn.r2_dev_subdomain:
            pytest.skip("No CDN domain configured")
        url = client.get_cdn_url(bucket, "some/key.txt")
        assert url is not None
        # After the scheme (https://), there should be no run of "//"
        without_scheme = url.split("://", 1)[1]
        assert "//" not in without_scheme


# ── r2object & r2bucket dataclasses ───────────────────────────────────────────


class TestDataclasses:
    def test_r2object_name_for_regular_file(self):
        obj = R2Object(key="folder/sub/file.txt")
        assert obj.name == "file.txt"

    def test_r2object_name_for_folder(self):
        folder = R2Object(key="folder/sub/", is_folder=True)
        assert folder.name == "sub/"

    def test_r2object_name_top_level_file(self):
        obj = R2Object(key="toplevel.txt")
        assert obj.name == "toplevel.txt"

    def test_r2object_defaults(self):
        obj = R2Object(key="test.bin")
        assert obj.size == 0
        assert obj.last_modified is None
        assert obj.etag == ""
        assert obj.content_type == ""
        assert obj.is_folder is False

    def test_r2bucket_defaults(self):
        b = R2Bucket(name="my-bucket")
        assert b.name == "my-bucket"
        assert b.creation_date is None

    def test_list_objects_result_defaults(self):
        result = ListObjectsResult()
        assert result.objects == []
        assert result.folders == []
        assert result.prefix == ""
