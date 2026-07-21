"""Shared Streamlit state: the singleton JobManager + settings."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from jobs import JobManager
from paths import SETTINGS


@st.cache_resource
def get_manager() -> JobManager:
    """One JobManager shared across all reruns and browser sessions."""
    cap = 2
    if SETTINGS.exists():
        try:
            cap = int(json.loads(SETTINGS.read_text()).get("cpu_cap", 2))
        except Exception:
            pass
    return JobManager(cpu_cap=cap)


def get_settings() -> dict:
    if SETTINGS.exists():
        try:
            return json.loads(SETTINGS.read_text())
        except Exception:
            return {}
    return {}
