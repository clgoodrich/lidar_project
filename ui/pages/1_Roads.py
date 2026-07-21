"""Roads page: inference, sweep training, aggregation, orientation labels."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from registry import by_group
from widgets import render_task

st.set_page_config(page_title="Roads · WellSight", page_icon="🛣️",
                   layout="wide")
st.title("🛣️ Roads")
st.caption("Run road models, train sweep variants, aggregate results. GPU jobs "
           "queue one at a time; watch them on the Jobs page.")

for task in by_group("Roads"):
    render_task(task)
