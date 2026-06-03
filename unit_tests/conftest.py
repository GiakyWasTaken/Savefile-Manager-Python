"""Pytest configuration for unit tests."""

import sys
from pathlib import Path

# Ensure the repository root is on sys.path so tests can import project modules
ROOT = Path(__file__).resolve().parent.parent
root_str = str(ROOT)

if root_str not in sys.path:
    sys.path.insert(0, root_str)
