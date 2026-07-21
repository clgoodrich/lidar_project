"""Analysis page: provenance, well-age, pad bins, photo sources (CPU tasks)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from registry import by_group
from widgets import render_task

st.set_page_config(page_title="Analysis · WellSight", page_icon="📊",
                   layout="wide")
st.title("📊 Analysis")
st.caption("Cross-reference and characterization jobs. These are CPU-only and "
           "safe to run while a GPU training is in flight.")

for task in by_group("Analysis"):
    render_task(task)
