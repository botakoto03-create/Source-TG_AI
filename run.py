import sys
from telegram_organizer.main import run

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
# source-TG