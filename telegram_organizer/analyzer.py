from pathlib import Path


IMAGE_EXTENSIONS = frozenset(
    [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".heic", ".heif"]
)
VIDEO_EXTENSIONS = frozenset(
    [".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".wmv", ".m4v", ".3gp", ".ts"]
)
_HEIF_BRANDS = frozenset(
    ["heic", "heix", "hevc", "hevx", "mif1", "msf1", "avif", "avis"]
)


def _read_header(path: Path, n: int = 16) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read(n)
    except OSError:
        return b""


def _ftyp_brand(header: bytes) -> str:
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return header[8:12].decode("latin-1", errors="replace").strip().lower()
    return ""


def analyze_file(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    header = _read_header(path)

    if not header:
        return "unknown", suffix or ".bin"

    if len(header) >= 12 and header[:4] == b"RIFF":
        if header[8:12] == b"WEBP":
            return "image", suffix if suffix in IMAGE_EXTENSIONS else ".webp"
        if header[8:12] == b"AVI ":
            return "video", suffix if suffix in VIDEO_EXTENSIONS else ".avi"
        
    brand = _ftyp_brand(header)
    if brand:
        if brand in _HEIF_BRANDS:
            return "image", suffix if suffix in IMAGE_EXTENSIONS else ".heic"
        return "video", suffix if suffix in VIDEO_EXTENSIONS else ".mp4"

    if header[:3] == b"\xff\xd8\xff":
        return "image", suffix if suffix in IMAGE_EXTENSIONS else ".jpg"

    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "image", suffix if suffix in IMAGE_EXTENSIONS else ".png"

    if header[:6] in (b"GIF87a", b"GIF89a"):
        return "image", suffix if suffix in IMAGE_EXTENSIONS else ".gif"

    if header[:2] == b"BM":
        return "image", suffix if suffix in IMAGE_EXTENSIONS else ".bmp"

    if header[:4] in (b"\x49\x49\x2a\x00", b"\x4d\x4d\x00\x2a"):
        return "image", suffix if suffix in IMAGE_EXTENSIONS else ".tiff"

    if header[:4] == b"\x1a\x45\xdf\xa3":
        return "video", suffix if suffix in VIDEO_EXTENSIONS else ".mkv"

    if header[:3] == b"FLV":
        return "video", suffix if suffix in VIDEO_EXTENSIONS else ".flv"

    if header[:4] == b"\x30\x26\xb2\x75":
        return "video", suffix if suffix in VIDEO_EXTENSIONS else ".wmv"

    if suffix in IMAGE_EXTENSIONS:
        return "image", suffix
    if suffix in VIDEO_EXTENSIONS:
        return "video", suffix

    return "unknown", suffix or ".bin"
