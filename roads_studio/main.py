"""Roads Studio entry point.

    python -m roads_studio.main

Opens a local browser at http://127.0.0.1:8090/ and serves the knob board.
"""
from __future__ import annotations

from nicegui import ui

from roads_studio.app import build

PORT = 8095  # 8090 is a Windows-reserved (excluded) port — do not use


def _open_browser(url: str) -> None:
    """Open in the OS default browser (Python's webbrowser mis-routes to IE on
    Windows; os.startfile respects the real per-user default)."""
    import os
    import threading

    def _go():
        try:
            os.startfile(url)  # noqa: S606 (Windows shell open)
        except Exception:
            import webbrowser

            webbrowser.open(url)

    threading.Timer(1.0, _go).start()


def run() -> None:
    import os

    build()
    if not os.environ.get("ROADS_STUDIO_NOBROWSER"):
        _open_browser(f"http://127.0.0.1:{PORT}/")
    ui.run(
        host="127.0.0.1",
        port=PORT,
        title="Roads Studio",
        reload=False,
        show=False,
    )


# NiceGUI needs ui.run() to execute at import under __mp_main__ / __main__.
run()
