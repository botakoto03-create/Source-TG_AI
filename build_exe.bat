@echo off
REM
REM
REM
REM
REM

echo Installing PyInstaller (skipped if already present)...
pip install --quiet pyinstaller

echo.
echo Building telegram-organizer.exe ...
pyinstaller ^
  --onefile ^
  --console ^
  --name "telegram-organizer" ^
  --icon NONE ^
  run.py

echo.
if exist dist\telegram-organizer.exe (
    echo  Build successful!
    echo  Output: dist\telegram-organizer.exe
) else (
    echo  Build failed — check the output above.
    exit /b 1
)
