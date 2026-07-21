"""Roads Studio — NiceGUI knob board for road extraction.

Pick a block + model, turn the knobs, watch the roads redraw over the
hillshade, export the layer you like to GeoPackage for QGIS. The extraction
engine is ``roads_studio.core`` (a thin wrapper over the existing
``_road_optimize`` pipeline) — this file is only UI + wiring.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from nicegui import run, ui

from roads_studio import core

SOURCES = core.discover()
BLOCKS = sorted(SOURCES.keys())
SCALE = {"Full (slow)": 1, "Half": 2, "Quarter (fast)": 4}

# knobs that change what raster we load (force a reload when they change)
LOAD_KEYS = ("block", "model", "use_drainage", "scale")


@dataclass
class Studio:
    """Per-client UI state + the render loop."""

    # widgets filled in during build
    image: object = None
    stat: object = None
    spinner: object = None
    model_sel: object = None

    loaded: object = None          # core.Loaded (cached)
    loaded_sig: tuple = None       # signature the cached Loaded was built for
    rendering: bool = False
    dirty: bool = False
    controls: dict = field(default_factory=dict)  # name -> widget
    _timer: object = None

    # ---- read current control values ------------------------------------
    def vals(self) -> dict:
        c = self.controls
        return {k: (w.value if hasattr(w, "value") else w) for k, w in c.items()}

    def current_source(self):
        v = self.vals()
        for s in SOURCES.get(v["block"], []):
            if s.model == v["model"]:
                return s
        opts = SOURCES.get(v["block"], [])
        return opts[0] if opts else None

    def ucfg(self) -> dict:
        v = self.vals()
        return dict(
            enhance=v["enhance"],
            thresh=v["thresh"],
            t=v["t"],
            lo=v["lo"],
            hi=v["hi"],
            slope_max=(v["slope_deg"] if v["slope_gate"] else None),
            pathopen=v["pathopen"],
            po_len_m=v["po_len_m"],
            min_area_m2=v["min_area_m2"],
            skel=v["skel"],
            spur=v["spur"],
            reconnect=v["reconnect"],
            island=v["island"],
        )

    # ---- debounced scheduling -------------------------------------------
    def schedule(self):
        if not self.controls.get("auto").value:
            return
        if self._timer is not None:
            self._timer.cancel()
        self._timer = ui.timer(0.45, lambda: self.render(), once=True)

    # ---- the render loop ------------------------------------------------
    async def render(self):
        if self.rendering:
            self.dirty = True          # coalesce — rerun after current pass
            return
        self.rendering = True
        self.spinner.set_visibility(True)
        try:
            while True:
                self.dirty = False
                src = self.current_source()
                if src is None:
                    self.stat.set_text("no source for this block")
                    return
                v = self.vals()
                scale = SCALE[v["scale"]]
                sig = (src.key, bool(v["use_drainage"]), scale)
                if sig != self.loaded_sig:
                    self.stat.set_text("loading raster…")
                    self.loaded = await run.io_bound(
                        core.load, src, bool(v["use_drainage"]), scale
                    )
                    self.loaded_sig = sig
                ucfg = self.ucfg()
                self.stat.set_text("extracting roads…")
                import time as _t

                t0 = _t.monotonic()
                gdf = await run.io_bound(core.extract, self.loaded, ucfg)
                png = await run.io_bound(
                    core.render_png, self.loaded, gdf, v["background"]
                )
                dt = _t.monotonic() - t0
                self.image.set_source(png)
                st = core.stats(gdf)
                self.stat.set_text(
                    f"{src.block} · {src.model}   —   "
                    f"{st['km']} km · {st['segments']} segments   "
                    f"({dt:.1f}s @ {v['scale'].split()[0].lower()} res)"
                )
                if not self.dirty:
                    break
        finally:
            self.rendering = False
            self.spinner.set_visibility(False)

    async def export(self):
        src = self.current_source()
        if src is None:
            ui.notify("no source selected", type="warning")
            return
        v = self.vals()
        ui.notify("rendering full-resolution layer for export…")
        try:
            full = await run.io_bound(core.load, src, bool(v["use_drainage"]), 1)
            gdf = await run.io_bound(core.extract, full, self.ucfg())
            from datetime import datetime

            # timestamp comes from the OS here (not a workflow), so it's fine
            tag = datetime.now().strftime("%m%d_%H%M%S")
            res = await run.io_bound(core.export, gdf, src, self.ucfg(), tag)
            ui.notify(
                f"exported {res['segments']} segments · {res['km']} km\n{res['gpkg']}",
                type="positive",
                multi_line=True,
                timeout=9000,
            )
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"export failed: {exc}", type="negative", multi_line=True)


def _model_options(block: str) -> list[str]:
    return [s.model for s in SOURCES.get(block, [])]


def build():
    @ui.page("/")
    def page():
        s = Studio()
        c = s.controls

        ui.query("body").style("background:#f4f6f8;")
        with ui.header().classes("items-center justify-between px-4 py-2").style(
            "background:#2f6f4f;"
        ):
            ui.label("Roads Studio").classes("text-xl font-semibold text-white")
            ui.label("tune the knobs → export the roads layer you want").classes(
                "text-sm text-white/80"
            )

        with ui.row().classes("w-full no-wrap gap-4 p-4"):
            # ---------------- LEFT: controls ---------------------------------
            with ui.column().classes("gap-3").style("width:380px; min-width:380px;"):
                with ui.card().classes("w-full"):
                    ui.label("Source").classes("text-sm font-bold text-gray-600")
                    c["block"] = ui.select(
                        BLOCKS, value=("613590" if "613590" in BLOCKS else BLOCKS[0]),
                        label="Block",
                    ).props("dense outlined").classes("w-full")
                    c["model"] = ui.select(
                        _model_options(c["block"].value),
                        value=_model_options(c["block"].value)[0],
                        label="Model",
                    ).props("dense outlined").classes("w-full")

                    def _on_block(_):
                        opts = _model_options(c["block"].value)
                        c["model"].options = opts
                        c["model"].value = opts[0] if opts else None
                        c["model"].update()
                        s.schedule()

                    c["block"].on_value_change(_on_block)
                    with ui.row().classes("w-full gap-2 items-center"):
                        c["scale"] = ui.select(
                            list(SCALE.keys()), value="Half", label="Preview res"
                        ).props("dense outlined").classes("flex-grow")
                        c["background"] = ui.select(
                            ["hillshade", "prob"], value="hillshade", label="Backdrop"
                        ).props("dense outlined").classes("flex-grow")
                    c["use_drainage"] = ui.checkbox(
                        "Suppress drainage (mask where drainage-prob wins)", value=True
                    )

                with ui.card().classes("w-full"):
                    ui.label("Extraction knobs").classes(
                        "text-sm font-bold text-gray-600"
                    )
                    c["enhance"] = ui.select(
                        ["none", "sato", "frangi", "meijering", "blend"],
                        value="none", label="Ridge enhance",
                    ).props("dense outlined").classes("w-full")

                    c["thresh"] = ui.select(
                        ["global", "otsu", "hysteresis"], value="global",
                        label="Threshold mode",
                    ).props("dense outlined").classes("w-full")

                    glob_box = ui.column().classes("w-full gap-0")
                    with glob_box:
                        _slider(c, "t", "Threshold", 0.05, 0.95, 0.05, 0.50)
                    hyst_box = ui.column().classes("w-full gap-0")
                    with hyst_box:
                        _slider(c, "lo", "Hysteresis low", 0.05, 0.9, 0.05, 0.30)
                        _slider(c, "hi", "Hysteresis high", 0.1, 0.95, 0.05, 0.60)

                    def _on_thresh(_):
                        glob_box.set_visibility(c["thresh"].value == "global")
                        hyst_box.set_visibility(c["thresh"].value == "hysteresis")
                        s.schedule()

                    c["thresh"].on_value_change(_on_thresh)

                    with ui.row().classes("w-full items-center gap-2"):
                        c["slope_gate"] = ui.checkbox("Slope gate ≤", value=False)
                        _slider(c, "slope_deg", "", 3, 45, 1, 20, compact=True)
                    with ui.row().classes("w-full items-center gap-2"):
                        c["pathopen"] = ui.checkbox("Path-open (kill blobs)", value=False)
                        _slider(c, "po_len_m", "len m", 4, 40, 1, 14, compact=True)

                    _slider(c, "min_area_m2", "Min blob area (m²)", 0, 400, 10, 40)
                    c["skel"] = ui.select(
                        ["zhang", "lee", "medial"], value="zhang",
                        label="Skeleton method",
                    ).props("dense outlined").classes("w-full")
                    _slider(c, "spur", "Prune spurs shorter than (m)", 0, 60, 5, 20)
                    c["reconnect"] = ui.select(
                        ["none", "lcp", "mst"], value="none",
                        label="Reconnect gaps",
                    ).props("dense outlined").classes("w-full")
                    _slider(c, "island", "Drop networks shorter than (m)", 0, 400, 10, 120)

                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        c["auto"] = ui.switch("Auto-render", value=True)
                        ui.button("Render", icon="refresh",
                                  on_click=lambda: s.render()).props("color=primary")
                    ui.button("Export layer for QGIS", icon="download",
                              on_click=lambda: s.export()).props(
                        "color=secondary outline").classes("w-full")

            # ---------------- RIGHT: preview ---------------------------------
            with ui.column().classes("flex-grow gap-2"):
                with ui.row().classes("items-center gap-3"):
                    s.spinner = ui.spinner(size="sm", color="primary")
                    s.spinner.set_visibility(False)
                    s.stat = ui.label("ready").classes("text-sm text-gray-600 font-mono")
                s.image = ui.image().classes("w-full rounded shadow").style(
                    "background:#111; min-height:400px;"
                )

        # wire every knob to the debounced scheduler
        for name, w in c.items():
            if name in ("block", "thresh"):  # have bespoke handlers above
                continue
            if hasattr(w, "on_value_change"):
                w.on_value_change(lambda _: s.schedule())

        hyst_box.set_visibility(False)  # start in global mode
        ui.timer(0.3, lambda: s.render(), once=True)  # first paint


def _slider(store: dict, key: str, label: str, lo, hi, step, default, compact=False):
    if label:
        ui.label(label).classes("text-xs text-gray-500 mt-1")
    sl = ui.slider(min=lo, max=hi, step=step, value=default).props(
        "label-always" if not compact else "label"
    ).classes("flex-grow" if compact else "w-full")
    store[key] = sl
    return sl
