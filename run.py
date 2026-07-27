import sys
from telegram_organizer.main import run

if __name__ == "__main__":
    try:
        run() # source-TG
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
