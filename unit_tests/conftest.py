"""Pytest configuration for unit tests."""

import sys
from pathlib import Path

# Ensure the repository root is on sys.path so tests can import project modules
ROOT = Path(__file__).resolve().parent.parent
ROOT_STR = str(ROOT)

if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)
