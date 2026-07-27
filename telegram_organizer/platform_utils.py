"""
Platform-specific helpers: Windows MTP via PowerShell, Android root discovery.
"""
import base64
import os
import subprocess
import sys
from pathlib import Path

from ._paths import ANDROID_ROOTS, ANDROID_RELATIVE


# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------

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
    } catch { Fail "Error navigating to '$seg': $_" }
    if (-not $next) { Fail "Path segment not found: '$seg'" }
    $cur = $next
    Info "-> $seg"
}

function Wait-Stable ([string]$path, [int]$stableSecs=8, [int]$maxSecs=300) {
    $prev    = -1
    $stable  = 0
    $elapsed = 0
    while ($elapsed -lt $maxSecs) {
        Start-Sleep -Seconds 1
        $elapsed++
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

    $files   = @()
    $folders = @()
    foreach ($item in $srcFolder.Items()) {
        if ($item.IsFolder) { $folders += $item }
        else                { $files   += $item }
    }

    if ($files.Count -gt 0) {
        $destNS = (New-Object -ComObject Shell.Application).Namespace($destPath)
        if (-not $destNS) {
            Log "WARN:Namespace null for $destPath — skipping"
        } else {
            $before = @(Get-ChildItem -LiteralPath $destPath -File -EA SilentlyContinue).Count
            foreach ($f in $files) { $destNS.CopyHere($f, 20) }
            Wait-Stable $destPath
            $after = @(Get-ChildItem -LiteralPath $destPath -File -EA SilentlyContinue).Count
            Log "COPIED:$($after - $before) file(s) -> $destPath"
        }
    }

    foreach ($sub in $folders) {
        Copy-Tree $sub.GetFolder "$destPath\$($sub.Name)"
    }
}

foreach ($fn in @("Telegram Images","Telegram Video")) {
    $src = $null
    foreach ($c in $cur.GetFolder.Items()) {
        if ($c.Name -eq $fn) { $src = $c; break }
    }
    if (-not $src) { Info "$fn — not found, skipping"; continue }
    Info "Copying $fn ..."
    Copy-Tree $src.GetFolder "$DestRoot\$fn"
    Info "Done: $fn"
}

Info "COMPLETE"
"""


def _drive_scan() -> Path | None:
    import string
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        try:
            if not root.exists():
                continue
            candidate = root / ANDROID_RELATIVE
            if candidate.exists():
                return candidate
        except OSError:
            pass
    return None


def _powershell_copy(device_name: str, dest_root: Path) -> bool:
    header = (
        f"$DeviceName = '{device_name.replace(chr(39), chr(39)*2)}'\n"
        f"$DestRoot   = '{str(dest_root).replace(chr(39), chr(39)*2)}'\n"
    )
    script  = header + _PS_BODY
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")

    cmd = [
        "powershell.exe", "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-EncodedCommand", encoded,
    ]

    completed = False
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
        for raw in proc.stdout:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("STATUS:"):
                msg = line[7:]
                if msg == "COMPLETE":
                    completed = True
                else:
                    print(f"  [PS] {msg}")
            elif line.startswith("COPIED:"):
                print(f"  ↓  {line[7:]}")
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
        print("  [ERROR] powershell.exe not found on PATH.")
    except Exception as exc:
        print(f"  [ERROR] PowerShell launch failed: {exc}")

    return completed


def build_windows_path() -> Path:
    print()
    device_name = input(
        "Device Name (exactly as shown in 'This PC'):\n> "
    ).strip()
    while not device_name:
        device_name = input("Cannot be empty:\n> ").strip()

    dest_root = (
        Path.cwd() / f"_mtp_{device_name.replace(' ', '_')}"
    ).resolve()
    dest_root.mkdir(exist_ok=True)

    print()
    print("─" * 44)
    print("Checking drive letters …")
    found = _drive_scan()
    if found:
        print(f"  Found on drive: {found}\n")
        return found
    print("  Not found on any drive letter.\n")

    print("Copying via PowerShell (Shell.Application) …")
    print(f"  Destination: {dest_root}")
    print("  Large caches may take several minutes — please wait.\n")
    if _powershell_copy(device_name, dest_root):
        print("\nPowerShell copy complete.\n")
        return dest_root
    
    print()
    print("─" * 44)
    print("[ERROR] Automatic copy failed.\n")
    user = os.getenv("USERNAME", "YourName")
    print("Manual fix — takes about 1 minute:\n")
    print(f"  1. Open Explorer → This PC → {device_name}")
    print("     → Internal shared storage → Android → data")
    print("     → org.telegram.messenger → files → Telegram\n")
    print("  2. Copy both folders:")
    print("       • Telegram Images")
    print("       • Telegram Video\n")
    print(f"  3. Paste them anywhere, e.g. C:\\Users\\{user}\\Desktop\\TelegramCache\\\n")
    print("  4. Re-run this program → choose option 3.")
    sys.exit(1)

def find_android_cache() -> Path | None:
    for root in ANDROID_ROOTS:
        p = Path(root)
        if p.exists():
            return p
    return None
