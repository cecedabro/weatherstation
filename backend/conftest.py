"""Ensure backend/ is on sys.path for contract tests imported via ../contract/tests."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
