import hashlib
import os
import shutil
from pathlib import Path

RENAME_PREFIX = "Secret-Archive"
TARGET_CACHE_FOLDERS = ("Telegram Images", "Telegram Video")

def sha256(path: Path) -> str | None:
    """Return the SHA-256 hex digest of *path*, or None on read error."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def next_counter(dest_dir: Path) -> int:
    existing: set[int] = set()
    if not dest_dir.exists():
        return 1
    prefix = f"{RENAME_PREFIX} ["
    for f in dest_dir.iterdir():
        stem = f.stem
        if stem.startswith(prefix) and stem.endswith("]"):
            try:
                existing.add(int(stem[len(prefix):-1]))
            except ValueError:
                pass
    return max(existing) + 1 if existing else 1


def make_name(counter: int, ext: str) -> str:
    return f"{RENAME_PREFIX} [{counter}]{ext.lower()}"


def do_copy(src: Path, dest_dir: Path, counter: int, ext: str) -> Path | None:
    """Copy *src* into *dest_dir* with the renamed filename; return dest or None."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / make_name(counter, ext)
    if dest.exists():
        return None
    try:
        shutil.copy2(src, dest)
        return dest
    except OSError as exc:
        print(f"  [ERROR] {src.name}: {exc}")
        return None


def scan_cache(folders: list[Path]) -> list[Path]:

    files: list[Path] = []
    for folder in folders:
        print(f"  Found: {folder.name}")
        try:
            for dirpath, _dirs, filenames in os.walk(folder):
                for fn in filenames:
                    files.append(Path(dirpath) / fn)
        except PermissionError as exc:
            print(f"  [WARN] Permission denied scanning {folder}: {exc}")
    return files


def find_cache_folders(root: Path) -> list[Path]:
    found: list[Path] = []
    if not root.exists():
        return found
    for child in root.iterdir():
        if child.is_dir() and child.name in TARGET_CACHE_FOLDERS:
            found.append(child)
    return found
