set -euo pipefail

echo "Installing PyInstaller (skipped if already present)..."
pip install --quiet pyinstaller

echo ""
echo "Building telegram-organizer ..."
pyinstaller \
  --onefile \
  --console \
  --name "telegram-organizer" \
  run.py

echo ""
if [ -f dist/telegram-organizer ]; then
  echo " Build successful!"
  echo " Output: dist/telegram-organizer"
else
  echo " Build failed — check the output above."
  exit 1
fi
