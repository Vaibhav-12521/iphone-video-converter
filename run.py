#!/usr/bin/env python3
"""Development entry point.

Run the application directly from source without installing it:

    python run.py

For a packaged, standalone build see ``build.py`` / ``README.md``.
"""
import sys
from pathlib import Path

# Make sure the project root (the folder that contains the ``movconv`` package)
# is importable regardless of the current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from movconv.app import main

if __name__ == "__main__":
    sys.exit(main())
