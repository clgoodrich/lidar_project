"""WellSight Control Panel — Streamlit entry (Dashboard).

Launch:  streamlit run ui/app.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from paths import ROOT, SWEEP
from state import get_manager

st.set_page_config(page_title="WellSight Control Panel", page_icon="🛢️",
                   layout="wide")


def gpu_status() -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,"
             "memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5).stdout.strip()
        util, used, total = [x.strip() for x in out.split(",")]
        return f"{util}% · {int(used)/1024:.1f}/{int(total)/1024:.1f} GB"
    except Exception:
        return "n/a"


def git_line() -> str:
    try:
        br = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        n = len(dirty.splitlines()) if dirty else 0
        return f"{br} ({n} uncommitted)" if n else f"{br} (clean)"
    except Exception:
        return "n/a"


mgr = get_manager()

# ---- sidebar ----
with st.sidebar:
    st.header("🛢️ WellSight")
    st.metric("GPU", gpu_status())
    free = shutil.disk_usage(ROOT).free / 1e9
    st.metric("Disk free (C:)", f"{free:.0f} GB",
              delta="low" if free < 50 else None,
              delta_color="inverse")
    running = [j for j in mgr.snapshot() if j.status == "running"]
    queued = [j for j in mgr.snapshot() if j.status == "queued"]
    st.metric("Jobs", f"{len(running)} running · {len(queued)} queued")
    st.caption(f"git: {git_line()}")
    if st.button("🔄 Refresh"):
        st.rerun()

# ---- main ----
st.title("Dashboard")

col1, col2, col3 = st.columns(3)
col1.metric("GPU", gpu_status())
col2.metric("Disk free", f"{free:.0f} GB")
col3.metric("Active jobs", len(running))
if free < 50:
    st.warning(f"Low disk: {free:.0f} GB free. Heavy rasters are gitignored "
               "but still fill the drive.")

# sweep panel
if SWEEP.exists():
    st.subheader("Road sweep (road_sweep_202607)")
    variants = ["cldice", "alpha078", "boundary", "orient", "res05"]
    cols = st.columns(len(variants))
    for c, v in zip(cols, variants):
        done = (SWEEP / v / "test_metrics.json").exists()
        c.metric(v, "✅ done" if done else "⏳ pending")
    lb = SWEEP / "leaderboard.md"
    if lb.exists():
        with st.expander("Leaderboard", expanded=True):
            st.markdown(lb.read_text(encoding="utf-8"))

# recent jobs
st.subheader("Recent jobs")
snap = mgr.snapshot()[:10]
if not snap:
    st.caption("No jobs yet. Go to **Roads** or **Analysis** to run something.")
else:
    rows = [{"id": j.id, "task": j.label, "status": j.status,
             "elapsed": f"{j.elapsed:.0f}s" if j.started else "-",
             "gpu": "🎛️" if j.gpu else "⚙️"} for j in snap]
    st.dataframe(rows, use_container_width=True, hide_index=True)

st.caption(f"Refreshed {time.strftime('%H:%M:%S')} · "
           "pages in the left nav · this window must stay open to watch "
           "progress (jobs keep running regardless).")
