"""Utility functions for file formatting, MIME detection, and icons."""

from __future__ import annotations

import mimetypes
from pathlib import Path

# File type icon mapping
ICON_MAP: dict[str, str] = {
    "folder": "📁",
    "image": "🖼️",
    "video": "🎬",
    "audio": "🎵",
    "pdf": "📄",
    "text": "📝",
    "code": "💻",
    "archive": "📦",
    "data": "💾",
    "unknown": "📎",
}

# Extensions grouped by category
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff"}
_VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv"}
_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma"}
_ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz"}
_CODE_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".sh",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
}
_DATA_EXTS = {".csv", ".sql", ".db", ".sqlite", ".parquet"}

MAX_OBJECT_SIZE = 10 * 1024 * 1024  # 10 MB


def get_file_category(filename: str) -> str:
    """Determine the category of a file based on its extension."""
    ext = Path(filename).suffix.lower()
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext == ".pdf":
        return "pdf"
    if ext in _ARCHIVE_EXTS:
        return "archive"
    if ext in _CODE_EXTS:
        return "code"
    if ext in _DATA_EXTS:
        return "data"
    if ext in {".txt", ".md", ".rst", ".log"}:
        return "text"
    return "unknown"


def get_file_icon(filename: str, is_folder: bool = False) -> str:
    """Get an icon for a file based on its type."""
    if is_folder:
        return ICON_MAP["folder"]
    category = get_file_category(filename)
    return ICON_MAP.get(category, ICON_MAP["unknown"])


def get_mime_type(filename: str) -> str:
    """Get the MIME type of a file."""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[unit_index]}"


def truncate_name(name: str, max_len: int = 40) -> str:
    """Truncate a name with ellipsis if too long."""
    if len(name) <= max_len:
        return name
    return name[: max_len - 3] + "..."
