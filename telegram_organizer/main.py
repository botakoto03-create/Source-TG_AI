import sys
from pathlib import Path

from .analyzer import analyze_file
from .copier import (
    do_copy,
    find_cache_folders,
    next_counter,
    scan_cache,
    sha256,
)
from .platform_utils import build_windows_path, find_android_cache

IMAGE_SUBDIR   = "image"
VIDEO_SUBDIR   = "video"
UNKNOWN_SUBDIR = "unknown"

def _banner() -> None:
    print("=" * 44)
    print("   Telegram Cache Media Organizer")
    print("=" * 44)
    print()


def select_platform() -> str:
    _banner()
    print("Select Mode\n")
    print("  1. Windows PC  (Android via USB/MTP)")
    print("  2. Android Phone / Tablet  (Termux / Pydroid)")
    print("  3. Local Folder  (already copied to this PC)")
    print()
    while True:
        raw = input("Choice:\n> ").strip()
        if raw in ("1", "2", "3"):
            return {"1": "windows", "2": "android", "3": "local"}[raw]
        print("Enter 1, 2, or 3.\n")


def ask_folder_name() -> str:
    print()
    name = input("Output Folder Name:\n> ").strip()
    while not name:
        name = input("Cannot be empty:\n> ").strip()
    return name


def ask_local_path() -> Path:
    print()
    print("Enter the path to the folder that contains")
    print("'Telegram Images' and/or 'Telegram Video'.")
    print("(Press Enter to use the current folder.)\n")
    raw = input("Path:\n> ").strip()
    return Path(raw).resolve() if raw else Path.cwd()


def print_summary(imgs: int, vids: int, unkn: int, dups: int, errs: int) -> None:
    print()
    print("═" * 44)
    print("  Finished" + (" Successfully" if errs == 0 else " with Errors"))
    print("═" * 44)
    print()
    print(f"  Images Copied       : {imgs}")
    print(f"  Videos Copied       : {vids}")
    print(f"  Unknown Copied      : {unkn}")
    print(f"  Duplicates Skipped  : {dups}")
    print(f"  Errors              : {errs}")
    print()


def run() -> None:
    mode        = select_platform()
    folder_name = ask_folder_name()

    print()
    print("Searching Telegram cache …")
    print()

    if mode == "windows":
        telegram_root = build_windows_path()

    elif mode == "android":
        telegram_root = find_android_cache()
        if not telegram_root:
            print()
            print("─" * 44)
            print("[!] Cannot access Telegram cache directly.")
            print()
            print("Android 10+ blocks access to /Android/data/")
            print("even with storage permission granted.")
            print()
            print("Fix — copy the Telegram folder to your")
            print("Downloads, then re-run and choose option 3:")
            print()
            print("  1. Install 'FX File Explorer' or any file")
            print("     manager that supports Android/data access")
            print("  2. Navigate to:")
            print("     Android/data/org.telegram.messenger")
            print("     /files/Telegram")
            print("  3. Copy 'Telegram Images' and 'Telegram Video'")
            print("     to your Downloads folder")
            print("  4. Re-run this program and choose option 3")
            print("     Path: /sdcard/Download")
            print("─" * 44)
            sys.exit(1)
        print(f"Found: {telegram_root}")

    else:
        telegram_root = ask_local_path()
        if not telegram_root.exists():
            print(f"[ERROR] Path not found: {telegram_root}")
            sys.exit(1)
        print(f"Reading from: {telegram_root}")

    cache_folders = find_cache_folders(telegram_root)
    if not cache_folders:
        print()
        print("[ERROR] Neither 'Telegram Images' nor 'Telegram Video' found.")
        if mode == "local":
            print(f"\nExpected sub-folders inside:\n  {telegram_root}")
        sys.exit(1)

    base_dir     = Path(folder_name)
    image_dest   = base_dir / IMAGE_SUBDIR
    video_dest   = base_dir / VIDEO_SUBDIR
    unknown_dest = base_dir / UNKNOWN_SUBDIR
    for d in (image_dest, video_dest, unknown_dest):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"[ERROR] Cannot create {d}: {exc}")
            sys.exit(1)


    print()
    print("Scanning …")
    print()
    all_files = scan_cache(cache_folders)
    print(f"\n  Total files: {len(all_files)}\n")

    img_ctr = next_counter(image_dest)
    vid_ctr = next_counter(video_dest)
    unk_ctr = next_counter(unknown_dest)

    seen: set[str] = set()
    imgs = vids = unkns = dups = errs = 0

    for fp in all_files:
        print(f"Analyzing  {fp.name}")
        mtype, ext = analyze_file(fp)
        print(f"  Type    : {mtype.capitalize()}  ({ext})")

        digest = sha256(fp)
        if digest is None:
            print("  [ERROR] Unreadable — skipping")
            errs += 1
            print()
            continue
        if digest in seen:
            print("  Duplicate — skipping")
            dups += 1
            print()
            continue
        seen.add(digest)

        print("  Copying …")
        if mtype == "image":
            dest = do_copy(fp, image_dest, img_ctr, ext)
            if dest:
                print(f"  ↓  {dest.name}")
                imgs += 1
                img_ctr += 1
            else:
                errs += 1
        elif mtype == "video":
            dest = do_copy(fp, video_dest, vid_ctr, ext)
            if dest:
                print(f"  ↓  {dest.name}")
                vids += 1
                vid_ctr += 1
            else:
                errs += 1
        else:
            dest = do_copy(fp, unknown_dest, unk_ctr, ext)
            if dest:
                print(f"  ↓  unknown/{dest.name}")
                unkns += 1
                unk_ctr += 1
            else:
                errs += 1
        print()

    print_summary(imgs, vids, unkns, dups, errs)
