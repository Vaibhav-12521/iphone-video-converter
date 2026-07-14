"""Allow running the package with ``python -m movconv``."""
import sys

from movconv.app import main

if __name__ == "__main__":
    sys.exit(main())
