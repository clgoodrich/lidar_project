"""Shared visual style: CSS injection + header/chip helpers.

Keeps every page consistent and hides Streamlit's default chrome so the app
reads as a purpose-built control panel rather than a dev tool.
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
/* hide Streamlit chrome */
#MainMenu, footer, header [data-testid="stToolbar"] {visibility:hidden;}
[data-testid="stDecoration"] {display:none;}
[data-testid="stStatusWidget"] {display:none;}

/* tighter, calmer page */
.block-container {padding-top:2.2rem; padding-bottom:3rem; max-width:1180px;}
h1, h2, h3, h4 {letter-spacing:-0.01em;}

/* app header band */
.ws-head {display:flex; align-items:baseline; gap:.6rem; margin-bottom:.2rem;}
.ws-head .ws-title {font-size:1.5rem; font-weight:700; color:#1f2933;}
.ws-head .ws-sub {font-size:.9rem; color:#6b7280;}
.ws-rule {height:3px; width:52px; background:#2f6f4f; border-radius:3px;
          margin:.35rem 0 1.1rem;}

/* cards (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius:14px !important; border-color:#e6e9ee !important;
    box-shadow:0 1px 2px rgba(16,24,40,.04);
}

/* buttons */
.stButton>button {border-radius:9px; font-weight:600; padding:.4rem 1.1rem;}
.stButton>button[kind="primary"] {box-shadow:0 1px 2px rgba(47,111,79,.25);}

/* metric cards */
[data-testid="stMetric"] {background:#f8fafb; border:1px solid #eceff3;
    border-radius:12px; padding:.7rem .9rem;}
[data-testid="stMetricLabel"] {color:#6b7280;}

/* chips */
.ws-chip {display:inline-block; font-size:.72rem; font-weight:600;
    padding:.12rem .55rem; border-radius:999px; vertical-align:middle;}
.ws-gpu  {background:#eef4ff; color:#2456c9; border:1px solid #d6e2fb;}
.ws-cpu  {background:#eef7f0; color:#2f6f4f; border:1px solid #d6eadd;}
.ws-ok   {background:#eaf6ec; color:#227a3b;}
.ws-run  {background:#fff5e6; color:#b26a00;}
.ws-wait {background:#f0f2f5; color:#6b7280;}
.ws-fail {background:#fdecec; color:#b42318;}

/* radios/checkboxes a touch tighter */
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label {font-size:.9rem;}
.stCode {font-size:.78rem;}
</style>
"""

_STATUS = {"running": ("ws-run", "running"), "queued": ("ws-wait", "queued"),
           "done": ("ws-ok", "done"), "failed": ("ws-fail", "failed"),
           "cancelled": ("ws-wait", "cancelled"),
           "orphaned": ("ws-fail", "orphaned")}


def inject():
    st.markdown(_CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str = ""):
    st.markdown(
        f'<div class="ws-head"><span class="ws-title">{title}</span>'
        f'<span class="ws-sub">{subtitle}</span></div><div class="ws-rule">'
        "</div>", unsafe_allow_html=True)


def chip(text: str, kind: str) -> str:
    return f'<span class="ws-chip ws-{kind}">{text}</span>'


def status_chip(status: str) -> str:
    cls, label = _STATUS.get(status, ("ws-wait", status))
    return f'<span class="ws-chip {cls}">{label}</span>'
