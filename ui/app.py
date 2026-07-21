"""WellSight Control Panel — Streamlit entry (Dashboard).

Launch:  streamlit run ui/app.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from paths import ROOT, SWEEP
from state import get_manager
from style import header, inject, status_chip

st.set_page_config(page_title="WellSight Control Panel", page_icon="🛢️",
                   layout="wide")
inject()


def gpu_status():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,"
             "memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5).stdout.strip()
        util, used, total = [x.strip() for x in out.split(",")]
        return f"{util}%", f"{int(used)/1024:.1f}/{int(total)/1024:.1f} GB"
    except Exception:
        return "n/a", ""


def git_line():
    try:
        br = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        n = len(dirty.splitlines()) if dirty else 0
        return f"{br} · {n} uncommitted" if n else f"{br} · clean"
    except Exception:
        return "n/a"


mgr = get_manager()
snap = mgr.snapshot()
running = [j for j in snap if j.status == "running"]
queued = [j for j in snap if j.status == "queued"]
free = shutil.disk_usage(ROOT).free / 1e9
util, vram = gpu_status()

with st.sidebar:
    st.markdown("### 🛢️ WellSight")
    st.caption("LiDAR orphaned-well control panel")
    st.divider()
    st.metric("GPU", util, vram or None)
    st.metric("Disk free", f"{free:.0f} GB",
              "low" if free < 50 else None, delta_color="inverse")
    st.metric("Jobs", f"{len(running)} running",
              f"{len(queued)} queued" if queued else None)
    st.caption(f"git: {git_line()}")
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

header("Dashboard", "at-a-glance status")

c = st.columns(4)
c[0].metric("GPU utilization", util)
c[1].metric("VRAM", vram or "—")
c[2].metric("Disk free (C:)", f"{free:.0f} GB")
c[3].metric("Active jobs", f"{len(running)}")
if free < 50:
    st.warning(f"Low disk: {free:.0f} GB free. Heavy rasters are gitignored "
               "but still consume the drive.")

if SWEEP.exists():
    st.markdown("#### Road sweep")
    with st.container(border=True):
        variants = ["cldice", "alpha078", "boundary", "orient", "res05"]
        cols = st.columns(len(variants))
        for col, v in zip(cols, variants):
            done = (SWEEP / v / "test_metrics.json").exists()
            col.markdown(f"**{v}**")
            col.markdown(status_chip("done" if done else "running"),
                         unsafe_allow_html=True)
        lb = SWEEP / "leaderboard.md"
        if lb.exists():
            st.markdown(lb.read_text(encoding="utf-8"))

st.markdown("#### Recent jobs")
if not snap:
    st.caption("No jobs yet — open **Roads** or **Analysis** in the left nav.")
else:
    with st.container(border=True):
        for j in snap[:8]:
            row = st.columns([3, 1.2, 1, 1])
            row[0].write(j.label)
            row[1].markdown(status_chip(j.status), unsafe_allow_html=True)
            row[2].caption("GPU" if j.gpu else "CPU")
            row[3].caption(f"{j.elapsed:.0f}s" if j.started else "—")

st.caption("This window must stay open to watch progress — jobs run detached "
           "and survive a restart.")
