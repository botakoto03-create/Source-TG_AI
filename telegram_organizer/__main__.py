import sys
from .main import run


def main() -> None:
    try:
        run()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()
