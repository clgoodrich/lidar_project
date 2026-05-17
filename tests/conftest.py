"""Test bootstrap.

Makes the repo root importable so test modules can ``import
notebooks.wellsight.preprocessing.cornrow_filter`` without an installed
package.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
