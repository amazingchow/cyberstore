"""Integration tests for OSSClient against a real Aliyun OSS instance.

Configuration is read from ~/.config/cyberstore/config.toml.
All tests are skipped when:
  - The config file does not exist
  - storage_provider is not 'oss'
  - OSS config is incomplete (missing endpoint, bucket, or credentials)

To run:
    pytest tests/test_oss_client.py -v
"""

from __future__ import annotations

import os
import tempfile

import pytest

from cyberstore.config import CONFIG_FILE, PROVIDER_OSS, AppConfig
from cyberstore.oss_client import OSSClient, OSSError, OSSSizeLimitError
from cyberstore.utils import MAX_OBJECT_SIZE

# ── skip guard ────────────────────────────────────────────────────────────────

_skip_reason: str | None = None

if not CONFIG_FILE.exists():
    _skip_reason = (
        f"Config file not found: {CONFIG_FILE}\n"
        "Create it by running `cyberstore` and completing the OSS setup, "
        "or write it manually:\n\n"
        "    [general]\n"
        "    storage_provider = 'oss'\n\n"
        "    [oss]\n"
        "    endpoint = 'https://oss-cn-<region>.aliyuncs.com'\n"
        "    bucket   = '<your-bucket>'\n"
        "    access_key_id     = '<AccessKeyId>'\n"
        "    access_key_secret = '<AccessKeySecret>'\n"
    )
else:
    _cfg = AppConfig.load()
    if _cfg.storage_provider != PROVIDER_OSS:
        _skip_reason = (
            f"storage_provider = '{_cfg.storage_provider}' in {CONFIG_FILE}. Set it to 'oss' to run OSS tests."
        )
    elif not _cfg.oss.is_valid():
        missing = [f for f in ("endpoint", "bucket", "access_key_id", "access_key_secret") if not getattr(_cfg.oss, f)]
        _skip_reason = f"OSS config incomplete — missing fields: {', '.join(missing)}"

pytestmark = pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")

# Prefix for all objects created during tests — makes cleanup easy and avoids
# collisions with real data.
_TEST_PREFIX = "_cyberstore_test_/"


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def cfg() -> AppConfig:
    return AppConfig.load()


@pytest.fixture(scope="module")
def client(cfg: AppConfig) -> OSSClient:
    return OSSClient(cfg)


@pytest.fixture(scope="module")
def bucket(cfg: AppConfig) -> str:
    return cfg.oss.bucket


# ── helpers ───────────────────────────────────────────────────────────────────


def _tmp_file(content: bytes, suffix: str = ".txt") -> str:
    """Write content to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, content)
    os.close(fd)
    return path


def _upload_and_cleanup(client: OSSClient, bucket: str, key: str, content: bytes) -> None:
    """Upload a temp file then remove the local copy."""
    path = _tmp_file(content)
    try:
        client.upload_file(bucket, path, key)
    finally:
        os.unlink(path)


# ── connection ────────────────────────────────────────────────────────────────


class TestConnection:
    def test_connection_succeeds(self, client: OSSClient):
        assert client.test_connection() is True

    def test_connection_detail_returns_true_and_message(self, client: OSSClient):
        ok, msg = client.test_connection_detail()
        assert ok is True
        assert isinstance(msg, str) and msg

    def test_wrong_credentials_returns_false(self, cfg: AppConfig):
        bad = AppConfig()
        bad.storage_provider = PROVIDER_OSS
        from cyberstore.config import OSSConfig

        bad.oss = OSSConfig(
            endpoint=cfg.oss.endpoint,
            bucket=cfg.oss.bucket,
            access_key_id="INVALID_KEY_ID",
            access_key_secret="INVALID_SECRET",
        )
        ok, msg = OSSClient(bad).test_connection_detail()
        assert ok is False
        assert msg


# ── upload ────────────────────────────────────────────────────────────────────


class TestUpload:
    def test_upload_text_file(self, client: OSSClient, bucket: str):
        key = _TEST_PREFIX + "upload_text.txt"
        path = _tmp_file(b"hello oss")
        try:
            client.upload_file(bucket, path, key)
            meta = client.head_object(bucket, key)
            assert meta["size"] == len(b"hello oss")
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)

    def test_upload_binary_file(self, client: OSSClient, bucket: str):
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

    def test_upload_zero_byte_file(self, client: OSSClient, bucket: str):
        key = _TEST_PREFIX + "upload_empty.txt"
        path = _tmp_file(b"")
        try:
            client.upload_file(bucket, path, key)
            meta = client.head_object(bucket, key)
            assert meta["size"] == 0
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)

    def test_upload_sets_content_type_for_known_extension(self, client: OSSClient, bucket: str):
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

    def test_upload_overwrites_existing_object(self, client: OSSClient, bucket: str):
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

    def test_upload_progress_callback_called(self, client: OSSClient, bucket: str):
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

    def test_upload_progress_callback_none_does_not_raise(self, client: OSSClient, bucket: str):
        key = _TEST_PREFIX + "upload_no_cb.txt"
        path = _tmp_file(b"no callback")
        try:
            client.upload_file(bucket, path, key, progress_callback=None)
        finally:
            os.unlink(path)
            client.delete_object(bucket, key)

    def test_upload_size_limit_raises(self, client: OSSClient, bucket: str):
        path = _tmp_file(b"x" * (MAX_OBJECT_SIZE + 1))
        try:
            with pytest.raises(OSSSizeLimitError):
                client.upload_file(bucket, path, _TEST_PREFIX + "too_large.bin")
        finally:
            os.unlink(path)

    def test_upload_key_with_nested_path(self, client: OSSClient, bucket: str):
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
    def test_download_matches_uploaded_content(self, client: OSSClient, bucket: str):
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

    def test_download_binary_file(self, client: OSSClient, bucket: str):
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

    def test_download_progress_callback_called(self, client: OSSClient, bucket: str):
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

    def test_download_nonexistent_key_raises(self, client: OSSClient, bucket: str):
        fd, local = tempfile.mkstemp()
        os.close(fd)
        try:
            with pytest.raises(OSSError):
                client.download_file(bucket, "_nonexistent_xyz_/missing.txt", local)
        finally:
            os.unlink(local)


# ── head_object ───────────────────────────────────────────────────────────────


class TestHeadObject:
    def test_head_returns_expected_fields(self, client: OSSClient, bucket: str):
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

    def test_head_nonexistent_key_raises(self, client: OSSClient, bucket: str):
        with pytest.raises(OSSError):
            client.head_object(bucket, "_nonexistent_xyz_/no_such_file.txt")

    def test_head_size_matches_content(self, client: OSSClient, bucket: str):
        for size in (0, 1, 1024, 8192):
            key = _TEST_PREFIX + f"head_size_{size}.bin"
            content = b"a" * size
            _upload_and_cleanup(client, bucket, key, content)
            try:
                assert client.head_object(bucket, key)["size"] == size
            finally:
                client.delete_object(bucket, key)


# ── list_objects ──────────────────────────────────────────────────────────────


class TestListObjects:
    def test_list_returns_result_object(self, client: OSSClient, bucket: str):
        result = client.list_objects(bucket, prefix="")
        assert hasattr(result, "objects")
        assert hasattr(result, "folders")
        assert isinstance(result.objects, list)
        assert isinstance(result.folders, list)

    def test_list_finds_uploaded_file(self, client: OSSClient, bucket: str):
        key = _TEST_PREFIX + "list_find/item.txt"
        _upload_and_cleanup(client, bucket, key, b"list find")
        try:
            result = client.list_objects(bucket, prefix=_TEST_PREFIX + "list_find/")
            assert any(o.key == key for o in result.objects)
        finally:
            client.delete_object(bucket, key)

    def test_list_with_prefix_shows_subfolder(self, client: OSSClient, bucket: str):
        key = _TEST_PREFIX + "list_folder/sub/file.txt"
        _upload_and_cleanup(client, bucket, key, b"subfolder")
        try:
            result = client.list_objects(bucket, prefix=_TEST_PREFIX + "list_folder/")
            folder_keys = [f.key for f in result.folders]
            assert any("sub" in k for k in folder_keys)
        finally:
            client.delete_object(bucket, key)

    def test_list_nonexistent_prefix_returns_empty(self, client: OSSClient, bucket: str):
        result = client.list_objects(bucket, prefix="_nonexistent_prefix_xyz_/")
        assert result.objects == []
        assert result.folders == []

    def test_list_folder_objects_have_is_folder_flag(self, client: OSSClient, bucket: str):
        key = _TEST_PREFIX + "list_flag/nested/deep.txt"
        _upload_and_cleanup(client, bucket, key, b"flag")
        try:
            result = client.list_objects(bucket, prefix=_TEST_PREFIX + "list_flag/")
            assert all(f.is_folder for f in result.folders)
            assert all(not o.is_folder for o in result.objects)
        finally:
            client.delete_object(bucket, key)

    def test_list_multiple_files_under_prefix(self, client: OSSClient, bucket: str):
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


# ── delete ────────────────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_object_removes_it(self, client: OSSClient, bucket: str):
        key = _TEST_PREFIX + "delete_single.txt"
        _upload_and_cleanup(client, bucket, key, b"to be deleted")
        client.delete_object(bucket, key)
        with pytest.raises(OSSError):
            client.head_object(bucket, key)

    def test_delete_nonexistent_object_does_not_raise(self, client: OSSClient, bucket: str):
        # S3 delete is idempotent
        client.delete_object(bucket, "_nonexistent_xyz_/ghost.txt")

    def test_delete_objects_bulk(self, client: OSSClient, bucket: str):
        keys = [_TEST_PREFIX + f"bulk_del_{i}.txt" for i in range(4)]
        paths = [_tmp_file(f"bulk {i}".encode()) for i in range(4)]
        for path, key in zip(paths, keys):
            client.upload_file(bucket, path, key)
            os.unlink(path)
        client.delete_objects(bucket, keys)
        for key in keys:
            with pytest.raises(OSSError):
                client.head_object(bucket, key)

    def test_delete_objects_empty_list_does_not_raise(self, client: OSSClient, bucket: str):
        client.delete_objects(bucket, [])


# ── presigned url ─────────────────────────────────────────────────────────────


class TestPresignedUrl:
    def test_presigned_url_is_valid_http_url(self, client: OSSClient, bucket: str):
        key = _TEST_PREFIX + "presign.txt"
        _upload_and_cleanup(client, bucket, key, b"presign content")
        try:
            url = client.generate_presigned_url(bucket, key)
            assert url.startswith("http")
            assert bucket in url or key in url
        finally:
            client.delete_object(bucket, key)

    def test_presigned_url_custom_expiry(self, client: OSSClient, bucket: str):
        key = _TEST_PREFIX + "presign_expiry.txt"
        _upload_and_cleanup(client, bucket, key, b"expiry test")
        try:
            url = client.generate_presigned_url(bucket, key, expiry=300)
            assert url.startswith("http")
        finally:
            client.delete_object(bucket, key)

    def test_presigned_url_accessible_via_http(self, client: OSSClient, bucket: str):
        """Verify that the presigned URL returns HTTP 200."""
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
    def test_cdn_url_none_when_no_cdn_configured(self, client: OSSClient, bucket: str, cfg: AppConfig):
        if cfg.cdn.custom_domain or cfg.cdn.r2_dev_subdomain:
            pytest.skip("CDN domain is configured — skipping 'no CDN' test")
        assert client.get_cdn_url(bucket, "some/key.txt") is None

    def test_cdn_url_uses_custom_domain(self, client: OSSClient, bucket: str, cfg: AppConfig):
        if not cfg.cdn.custom_domain:
            pytest.skip("No custom CDN domain configured")
        url = client.get_cdn_url(bucket, "path/to/file.png")
        assert url is not None
        assert "file.png" in url
        assert url.startswith("http")
