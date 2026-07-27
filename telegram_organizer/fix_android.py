from pathlib import Path
BASE = Path("/data/data/com.termux/files/home/Source-TG_AI/telegram_organizer")

(BASE / "platform_utils.py").write_text('''\
"""
Platform-specific helpers: Windows MTP via PowerShell, Android root discovery.
"""
import base64
import os
import subprocess
import sys
from pathlib import Path

from ._paths import ANDROID_ROOTS, ANDROID_RELATIVE

# Extra standard locations where Telegram saves media on modern Android
EXTRA_ANDROID_PATHS = [
    "/storage/emulated/0/Pictures/Telegram",
    "/storage/emulated/0/Movies/Telegram",
    "/storage/emulated/0/Download/Telegram",
    "/sdcard/Pictures/Telegram",
    "/sdcard/Movies/Telegram",
    "/sdcard/Download/Telegram",
]

_PS_BODY = r"""
$ProgressPreference    = 'SilentlyContinue'
$WarningPreference     = 'SilentlyContinue'
$ErrorActionPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'

function Log  ([string]$m) { [Console]::WriteLine($m) }
function Info ([string]$m) { Log "STATUS:$m" }
function Fail ([string]$m) { Log "ERROR:$m"; exit 1 }

try   { $sh = New-Object -ComObject Shell.Application }
catch { Fail "Cannot create Shell.Application: $_" }

$thisPC = $sh.Namespace(17)
if (-not $thisPC) { Fail "Cannot open This PC namespace" }

Info "Devices visible in This PC:"
$device = $null
foreach ($item in $thisPC.Items()) {
    Info "  [$($item.Name)]"
    if ($item.Name -eq $DeviceName) { $device = $item }
}
if (-not $device) { Fail "Device not found: '$DeviceName'" }
Info "Matched device: $($device.Name)"

$cur = $device
foreach ($seg in @("Internal shared storage","Android","data","org.telegram.messenger","files","Telegram")) {
    $next = $null
    try {
        foreach ($c in $cur.GetFolder.Items()) {
            if ($c.Name -eq $seg) { $next = $c; break }
        }
        if (-not $next) {
            foreach ($c in $cur.GetFolder.Items()) {
                if ($c.Name -like "*$seg*") { $next = $c; break }
            }
        }
    } catch { Fail "Error navigating to $seg : $_" }
    if (-not $next) { Fail "Path segment not found: $seg" }
    $cur = $next
    Info "-> $seg"
}

function Wait-Stable ([string]$path, [int]$stableSecs=8, [int]$maxSecs=300) {
    $prev = -1; $stable = 0; $elapsed = 0
    while ($elapsed -lt $maxSecs) {
        Start-Sleep -Seconds 1; $elapsed++
        $cur = @(Get-ChildItem -LiteralPath $path -File -Recurse -EA SilentlyContinue).Count
        if ($cur -eq $prev) { $stable++ } else { $stable = 0 }
        $prev = $cur
        if ($stable -ge $stableSecs) { return }
    }
}

function Copy-Tree ([object]$srcFolder, [string]$destPath) {
    if (-not (Test-Path $destPath)) {
        New-Item -ItemType Directory -Force -Path $destPath | Out-Null
    }
    $files = @(); $folders = @()
    foreach ($item in $srcFolder.Items()) {
        if ($item.IsFolder) { $folders += $item } else { $files += $item }
    }
    if ($files.Count -gt 0) {
        $destNS = (New-Object -ComObject Shell.Application).Namespace($destPath)
        if (-not $destNS) { Log "WARN:Namespace null for $destPath" }
        else {
            $before = @(Get-ChildItem -LiteralPath $destPath -File -EA SilentlyContinue).Count
            foreach ($f in $files) { $destNS.CopyHere($f, 20) }
            Wait-Stable $destPath
            $after = @(Get-ChildItem -LiteralPath $destPath -File -EA SilentlyContinue).Count
            Log "COPIED:$($after - $before) file(s) -> $destPath"
        }
    }
    foreach ($sub in $folders) {
        Copy-Tree $sub.GetFolder "$destPath\\$($sub.Name)"
    }
}

foreach ($fn in @("Telegram Images","Telegram Video")) {
    $src = $null
    foreach ($c in $cur.GetFolder.Items()) {
        if ($c.Name -eq $fn) { $src = $c; break }
    }
    if (-not $src) { Info "$fn not found, skipping"; continue }
    Info "Copying $fn ..."
    Copy-Tree $src.GetFolder "$DestRoot\\$fn"
    Info "Done: $fn"
}
Info "COMPLETE"
"""


def _drive_scan():
    import string
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\\\")
        try:
            if not root.exists():
                continue
            candidate = root / ANDROID_RELATIVE
            if candidate.exists():
                return candidate
        except OSError:
            pass
    return None


def _powershell_copy(device_name, dest_root):
    header = (
        f"$DeviceName = \'{device_name.replace(chr(39), chr(39)*2)}\'\\n"
        f"$DestRoot   = \'{str(dest_root).replace(chr(39), chr(39)*2)}\'\\n"
    )
    script  = header + _PS_BODY
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-EncodedCommand", encoded]
    completed = False
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace")
        for raw in proc.stdout:
            line = raw.rstrip("\\r\\n")
            if not line:
                continue
            if line.startswith("STATUS:"):
                msg = line[7:]
                if msg == "COMPLETE":
                    completed = True
                else:
                    print(f"  [PS] {msg}")
            elif line.startswith("COPIED:"):
                print(f"  v  {line[7:]}")
            elif line.startswith("ERROR:"):
                print(f"  [PS ERROR] {line[6:]}")
            elif line.startswith("WARN:"):
                print(f"  [PS WARN]  {line[5:]}")
        proc.wait()
        if not completed and proc.returncode != 0:
            err = (proc.stderr.read() or "").strip()
            if err:
                print(f"  [PS stderr] {err[:400]}")
    except FileNotFoundError:
        print("  [ERROR] powershell.exe not found.")
    except Exception as exc:
        print(f"  [ERROR] PowerShell launch failed: {exc}")
    return completed


def build_windows_path():
    print()
    device_name = input("Device Name (exactly as shown in This PC):\\n> ").strip()
    while not device_name:
        device_name = input("Cannot be empty:\\n> ").strip()
    dest_root = (Path.cwd() / f"_mtp_{device_name.replace(' ', '_')}").resolve()
    dest_root.mkdir(exist_ok=True)
    print()
    print("-" * 44)
    print("Checking drive letters ...")
    found = _drive_scan()
    if found:
        print(f"  Found on drive: {found}\\n")
        return found
    print("  Not found on any drive letter.\\n")
    print("Copying via PowerShell ...")
    print(f"  Destination: {dest_root}")
    print("  Large caches may take several minutes.\\n")
    if _powershell_copy(device_name, dest_root):
        print("\\nPowerShell copy complete.\\n")
        return dest_root
    user = os.getenv("USERNAME", "YourName")
    print("\\n[ERROR] Automatic copy failed.")
    print(f"  Manually copy Telegram folders to Desktop then re-run with option 3.")
    sys.exit(1)


def find_android_cache():
    """Return list of all accessible Telegram folders on this Android device."""
    found = []
    all_paths = ANDROID_ROOTS + EXTRA_ANDROID_PATHS
    for root in all_paths:
        p = Path(root)
        try:
            if p.exists():
                found.append(p)
        except PermissionError:
            pass
    return found
''')
print("platform_utils.py  OK")

(BASE / "main.py").write_text('''\
"""
Main entry point: interactive CLI that organises Telegram cache media.
"""
import sys
from pathlib import Path

from .analyzer import analyze_file
from .copier import do_copy, find_cache_folders, next_counter, scan_cache, sha256
from .platform_utils import build_windows_path, find_android_cache

IMAGE_SUBDIR   = "image"
VIDEO_SUBDIR   = "video"
UNKNOWN_SUBDIR = "unknown"


def _banner():
    print("=" * 44)
    print("   Telegram Cache Media Organizer")
    print("=" * 44)
    print()


def select_platform():
    _banner()
    print("Select Mode\\n")
    print("  1. Windows PC  (Android via USB/MTP)")
    print("  2. Android Phone / Tablet  (Termux / Pydroid)")
    print("  3. Local Folder  (already copied to this PC)")
    print()
    while True:
        raw = input("Choice:\\n> ").strip()
        if raw in ("1", "2", "3"):
            return {"1": "windows", "2": "android", "3": "local"}[raw]
        print("Enter 1, 2, or 3.\\n")


def ask_folder_name():
    print()
    name = input("Output Folder Name:\\n> ").strip()
    while not name:
        name = input("Cannot be empty:\\n> ").strip()
    return name


def ask_local_path():
    print()
    print("Enter the path to the folder that contains Telegram media.")
    print("(Press Enter to use the current folder.)\\n")
    raw = input("Path:\\n> ").strip()
    return Path(raw).resolve() if raw else Path.cwd()


def print_summary(imgs, vids, unkn, dups, errs):
    print()
    print("=" * 44)
    print("  Finished" + (" Successfully" if errs == 0 else " with Errors"))
    print("=" * 44)
    print()
    print(f"  Images Copied       : {imgs}")
    print(f"  Videos Copied       : {vids}")
    print(f"  Unknown Copied      : {unkn}")
    print(f"  Duplicates Skipped  : {dups}")
    print(f"  Errors              : {errs}")
    print()


def run():
    mode        = select_platform()
    folder_name = ask_folder_name()

    print()
    print("Searching Telegram cache ...")
    print()

    if mode == "windows":
        telegram_root = build_windows_path()
        cache_folders = find_cache_folders(telegram_root)

    elif mode == "android":
        roots = find_android_cache()
        if not roots:
            print("[ERROR] No Telegram folders found on this device.")
            sys.exit(1)
        # Use all found paths directly as source folders
        cache_folders = []
        for r in roots:
            print(f"Found: {r}")
            # If the folder contains Telegram Images / Video subfolders, use those
            subs = find_cache_folders(r)
            if subs:
                cache_folders.extend(subs)
            else:
                # Otherwise scan the folder itself
                cache_folders.append(r)

    else:  # local
        telegram_root = ask_local_path()
        if not telegram_root.exists():
            print(f"[ERROR] Path not found: {telegram_root}")
            sys.exit(1)
        print(f"Reading from: {telegram_root}")
        cache_folders = find_cache_folders(telegram_root)
        if not cache_folders:
            cache_folders = [telegram_root]

    if not cache_folders:
        print("[ERROR] No media folders found.")
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
    print("Scanning ...")
    print()
    all_files = scan_cache(cache_folders)
    print(f"\\n  Total files: {len(all_files)}\\n")

    img_ctr = next_counter(image_dest)
    vid_ctr = next_counter(video_dest)
    unk_ctr = next_counter(unknown_dest)

    seen = set()
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

        print("  Copying ...")
        if mtype == "image":
            dest = do_copy(fp, image_dest, img_ctr, ext)
            if dest:
                print(f"  v  {dest.name}")
                imgs += 1; img_ctr += 1
            else:
                errs += 1
        elif mtype == "video":
            dest = do_copy(fp, video_dest, vid_ctr, ext)
            if dest:
                print(f"  v  {dest.name}")
                vids += 1; vid_ctr += 1
            else:
                errs += 1
        else:
            dest = do_copy(fp, unknown_dest, unk_ctr, ext)
            if dest:
                print(f"  v  unknown/{dest.name}")
                unkns += 1; unk_ctr += 1
            else:
                errs += 1
        print()

    print_summary(imgs, vids, unkns, dups, errs)
''')
print("main.py            OK")
print()
print("All done. Run:  python3 run.py")
