"""Jobs page: queue table, live log viewer, progress, cancel/re-run."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from state import get_manager
from widgets import progress_from_log

st.set_page_config(page_title="Jobs · WellSight", page_icon="📋", layout="wide")
mgr = get_manager()

st.title("📋 Jobs")
top = st.columns([1, 1, 4])
if top[0].button("🔄 Refresh"):
    st.rerun()
auto = top[1].toggle("Auto-refresh (2s)", value=False)

snap = mgr.snapshot()
if not snap:
    st.caption("No jobs yet.")
    st.stop()

STATUS_ICON = {"running": "🟢", "queued": "⏳", "done": "✅", "failed": "❌",
               "cancelled": "⛔", "orphaned": "⚠️"}

rows = [{"": STATUS_ICON.get(j.status, "•"), "id": j.id, "task": j.label,
         "status": j.status, "gpu": "🎛️" if j.gpu else "⚙️",
         "elapsed": f"{j.elapsed:.0f}s" if j.started else "-",
         "commit": j.git_commit} for j in snap]
st.dataframe(rows, use_container_width=True, hide_index=True)

st.subheader("Inspect / control")
ids = [j.id for j in snap]
sel = st.selectbox("Job", ids, format_func=lambda i: f"{i} — "
                   f"{mgr.get(i).label} [{mgr.get(i).status}]")
job = mgr.get(sel)
if job:
    c = st.columns(4)
    c[0].write(f"**Status:** {job.status}")
    c[1].write(f"**GPU:** {'yes' if job.gpu else 'no'}")
    c[2].write(f"**Elapsed:** {job.elapsed:.0f}s")
    c[3].write(f"**rc:** {job.returncode}")
    if job.status in ("running", "queued"):
        if st.button("⛔ Cancel", type="secondary"):
            mgr.cancel(sel)
            st.rerun()
    with st.expander("Command", expanded=False):
        st.code(" ".join(job.cmd), language="bash")

    log = mgr.tail(sel, n=400)
    prog = progress_from_log(log)
    if prog:
        st.progress(prog[0], text=prog[1])
    st.text_area("Log (tail)", log, height=420, key=f"log:{sel}")

if auto:
    time.sleep(2)
    st.rerun()
