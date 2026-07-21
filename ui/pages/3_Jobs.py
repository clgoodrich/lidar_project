"""Jobs page: queue list, live log viewer, progress, cancel."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from state import get_manager
from style import header, inject, status_chip
from widgets import progress_from_log

st.set_page_config(page_title="Jobs · WellSight", page_icon="📋", layout="wide")
inject()
mgr = get_manager()

header("Jobs", "queue · logs · progress")

bar = st.columns([1, 1.4, 5])
if bar[0].button("🔄 Refresh", use_container_width=True):
    st.rerun()
auto = bar[1].toggle("Auto-refresh 2s", value=False)

snap = mgr.snapshot()
if not snap:
    st.info("No jobs yet. Run something from **Roads** or **Analysis**.")
    st.stop()

left, right = st.columns([1, 1.6])

with left:
    st.markdown("##### Queue")
    for j in snap[:20]:
        with st.container(border=True):
            r = st.columns([3, 1.4])
            r[0].write(f"**{j.label}**")
            r[0].caption(f"`{j.id}` · {'GPU' if j.gpu else 'CPU'} · "
                         f"{j.elapsed:.0f}s" if j.started else f"`{j.id}`")
            r[1].markdown(status_chip(j.status), unsafe_allow_html=True)
            if j.status in ("running", "queued"):
                if r[1].button("Cancel", key=f"c:{j.id}"):
                    mgr.cancel(j.id)
                    st.rerun()

with right:
    st.markdown("##### Log")
    ids = [j.id for j in snap]
    default = st.session_state.get("_last_job", ids[0])
    sel = st.selectbox("Job", ids, index=ids.index(default) if default in ids
                       else 0, format_func=lambda i:
                       f"{mgr.get(i).label} · {mgr.get(i).status}")
    job = mgr.get(sel)
    if job:
        log = mgr.tail(sel, n=400)
        prog = progress_from_log(log)
        if prog:
            st.progress(prog[0], text=prog[1])
        st.code(log or "(no output yet)", language="log", height=460)

if auto:
    time.sleep(2)
    st.rerun()
