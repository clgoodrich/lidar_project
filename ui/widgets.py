"""Shared widget helpers: render a Task as a clean card with a Run/Queue action."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from registry import Inp, Task
from state import get_manager
from style import chip

_EP = re.compile(r"ep\s+(\d+)\s*/\s*(\d+)")


def _widget(inp: Inp, key: str):
    opts = inp.options()
    if inp.kind == "radio":
        return st.radio(inp.label, opts, key=key, help=inp.help,
                        index=opts.index(inp.default) if inp.default in opts
                        else 0, horizontal=len(opts) <= 4)
    if inp.kind == "select":
        return st.selectbox(inp.label, opts, key=key, help=inp.help,
                            index=opts.index(inp.default) if inp.default in opts
                            else 0)
    if inp.kind == "multiselect":
        return st.multiselect(inp.label, opts, key=key, help=inp.help)
    if inp.kind == "int":
        return st.number_input(inp.label, value=int(inp.default or 0),
                               min_value=int(inp.minv), max_value=int(inp.maxv),
                               step=1, key=key, help=inp.help)
    if inp.kind == "slider":
        return st.slider(inp.label, float(inp.minv), float(inp.maxv),
                         float(inp.default), float(inp.step), key=key,
                         help=inp.help)
    if inp.kind == "flag":
        return st.checkbox(inp.label, value=bool(inp.default), key=key,
                           help=inp.help)
    return st.text_input(inp.label, value=str(inp.default or ""), key=key)


def render_task(task: Task):
    """One task = one bordered card: title + chip, form fields, action row."""
    with st.container(border=True):
        head = st.columns([8, 1.4])
        head[0].markdown(f"#### {task.label}")
        head[1].markdown(
            chip("GPU", "gpu") if task.gpu else chip("CPU", "cpu"),
            unsafe_allow_html=True)
        if task.note:
            st.caption(task.note)

        values = {}
        # lay form fields across up to 3 columns for a compact card
        simple = [i for i in task.inputs]
        if simple:
            ncol = min(3, len(simple))
            cols = st.columns(ncol)
            for i, inp in enumerate(simple):
                with cols[i % ncol]:
                    values[inp.name] = _widget(inp, key=f"{task.id}:{inp.name}")

        try:
            args = task.build(values)
        except Exception as e:
            st.error(f"cannot build command: {e}")
            return
        missing = [p for p in task.requires(values) if not Path(p).exists()]
        outs = task.outputs(values)

        st.divider()
        act = st.columns([1.3, 2, 2])
        disabled = bool(missing) or not task.script_abs.exists()
        label = "Queue ▸" if task.gpu else "Run ▸"
        if act[0].button(label, key=f"run:{task.id}", disabled=disabled,
                         type="primary", use_container_width=True):
            mgr = get_manager()
            jid = mgr.submit(task_id=task.id, label=task.label,
                             script=task.script, args=args, gpu=task.gpu,
                             params=values)
            st.session_state["_last_job"] = jid
            st.toast(f"Queued {jid}", icon="✅")
            st.success(f"Submitted **{jid}** → watch it on **Jobs**.")
        with act[1].popover("Command", use_container_width=True):
            st.code(f"python -u {task.script} " + " ".join(args),
                    language="bash")
            if task.docs:
                st.caption(f"docs: `{task.docs}`")
            if outs:
                st.caption("outputs → " + ", ".join(f"`{o}`" for o in outs))
        if missing:
            act[2].caption("⚠ missing: " +
                           ", ".join(f"`{Path(m).name}`" for m in missing))
        elif outs:
            act[2].caption("→ " + f"`{Path(outs[0]).name}`")


def progress_from_log(text: str):
    last = None
    for m in _EP.finditer(text):
        last = m
    if not last:
        return None
    cur, tot = int(last.group(1)), int(last.group(2))
    return cur / max(tot, 1), f"epoch {cur}/{tot}"
