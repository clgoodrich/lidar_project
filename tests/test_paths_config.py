"""The _common fallback must not drift from config/paths.toml.

`_common._DEFAULTS` is what the project falls back to when config/paths.toml is
missing or unparseable. That makes it a silent hazard: it went stale across the
2026-08-13 area-major move and would have pointed a broken-config run at
data/derivatives, a directory that no longer exists. Nothing would have raised --
paths would just have resolved to somewhere empty.

A fallback nobody checks is worse than no fallback.
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))

from _common import _DEFAULTS, PATHS  # noqa: E402


def _config() -> dict:
    return tomllib.loads((ROOT / "config" / "paths.toml").read_text("utf8"))["paths"]


def test_defaults_match_config_exactly():
    assert _DEFAULTS == _config(), (
        "_common._DEFAULTS has drifted from config/paths.toml. Regenerate it "
        "rather than hand-patching, so the fallback cannot describe a layout "
        "that no longer exists."
    )


@pytest.mark.parametrize("key", sorted(_config()))
def test_every_configured_path_exists(key):
    p = PATHS[key]
    assert p.exists(), f"config key {key!r} points at {p}, which does not exist"
