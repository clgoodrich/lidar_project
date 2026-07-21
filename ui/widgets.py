"""Shared widget helpers: render a Task form and its Run/Queue control."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from registry import Inp, Task
from state import get_manager

_EP = re.compile(r"ep\s+(\d+)\s*/\s*(\d+)")


def _widget(inp: Inp, key: str):
    opts = inp.options()
    if inp.kind == "radio":
        return st.radio(inp.label, opts, key=key, help=inp.help,
                        index=opts.index(inp.default) if inp.default in opts
                        else 0)
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
    """Render a task's form inside an expander with a Run/Queue button."""
    icon = "🎛️" if task.gpu else "⚙️"
    with st.expander(f"{icon} {task.label}", expanded=False):
        if task.note:
            st.caption(task.note)
        values = {}
        for inp in task.inputs:
            values[inp.name] = _widget(inp, key=f"{task.id}:{inp.name}")

        # requires-check
        missing = [p for p in task.requires(values)
                   if not Path(p).exists()]
        try:
            args = task.build(values)
        except Exception as e:
            st.error(f"cannot build command: {e}")
            return

        # for flag inputs, translate True -> flag string here so preview matches
        flag_args = []
        for inp in task.inputs:
            if inp.kind == "flag" and values.get(inp.name) and inp.flag:
                if inp.flag not in args:
                    flag_args.append(inp.flag)
        full = args  # builders already include flags where relevant

        cmd_str = f"python -u {task.script} " + " ".join(full)
        st.code(cmd_str, language="bash")

        if missing:
            st.warning("Missing inputs (Run disabled):\n" +
                       "\n".join(f"- `{m}`" for m in missing))

        out_note = task.outputs(values)
        if out_note:
            st.caption("Outputs → " + ", ".join(f"`{o}`" for o in out_note))

        c1, c2 = st.columns([1, 3])
        disabled = bool(missing) or not task.script_abs.exists()
        label = "Queue (GPU)" if task.gpu else "Run"
        if c1.button(label, key=f"run:{task.id}", disabled=disabled,
                     type="primary"):
            mgr = get_manager()
            jid = mgr.submit(task_id=task.id, label=task.label,
                             script=task.script, args=full, gpu=task.gpu,
                             params=values)
            st.success(f"Submitted job `{jid}` → see **Jobs** page.")
        if task.docs:
            c2.caption(f"docs: `{task.docs}`")


def progress_from_log(text: str) -> tuple[float, str] | None:
    """Best-effort epoch progress from a training log tail."""
    last = None
    for m in _EP.finditer(text):
        last = m
    if not last:
        return None
    cur, tot = int(last.group(1)), int(last.group(2))
    return cur / max(tot, 1), f"epoch {cur}/{tot}"
