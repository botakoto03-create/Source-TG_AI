import hashlib
import shutil
from pathlib import Path

RENAME_PREFIX = "Secret-Archive"
TARGET_CACHE_FOLDERS = ("Telegram Images", "Telegram Video")


def sha256(path: Path) -> str | None:
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
        for item in folder.rglob("*"):
            if item.is_file():
                files.append(item)
    return files


def find_cache_folders(root: Path) -> list[Path]:
    found: list[Path] = []
    if not root.exists():
        return found
    for child in root.iterdir():
        if child.is_dir() and child.name in TARGET_CACHE_FOLDERS:
            found.append(child)
    return found
