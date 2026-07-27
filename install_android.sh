set -euo pipefail

echo "Updating Termux packages..."
pkg update -y && pkg upgrade -y

echo "Installing Python..."
pkg install -y python

echo "Installing the organizer..."
pip install --quiet .

echo ""
echo "Done! Run the organizer any time with:"
echo "  telegram-organizer"
echo ""
echo "Or run directly without installing:"
echo "  python run.py"
