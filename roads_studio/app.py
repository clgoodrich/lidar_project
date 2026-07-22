"""Roads Studio — NiceGUI app with two tabs.

  Extract   — knob board: tune post-processing of a road-prob raster, redraw
              over the hillshade, export the layer to GeoPackage for QGIS.
  Model Lab — train a road U-Net variant (recreate cldice or design a new one):
              set hyperparameters, launch a GPU run, watch the loss curve; the
              finished model auto-appears in the Extract model dropdown.

Engines live in ``roads_studio.core`` (extraction) and ``roads_studio.train``
(training driver). This file is UI + wiring only.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from nicegui import run, ui

from roads_studio import core, train

SOURCES = core.discover()
BLOCKS = sorted(SOURCES.keys())
SCALE = {"Full (slow)": 1, "Half": 2, "Quarter (fast)": 4}


def rescan_sources():
    global SOURCES, BLOCKS
    SOURCES = core.discover()
    BLOCKS = sorted(SOURCES.keys())


# ===========================================================================
# Extract tab
# ===========================================================================
@dataclass
class Studio:
    image: object = None
    stat: object = None
    spinner: object = None
    loaded: object = None
    loaded_sig: tuple = None
    rendering: bool = False
    dirty: bool = False
    controls: dict = field(default_factory=dict)
    _timer: object = None

    def vals(self) -> dict:
        return {k: w.value for k, w in self.controls.items() if hasattr(w, "value")}

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
            enhance=v["enhance"], thresh=v["thresh"], t=v["t"], lo=v["lo"], hi=v["hi"],
            slope_max=(v["slope_deg"] if v["slope_gate"] else None),
            pathopen=v["pathopen"], po_len_m=v["po_len_m"],
            min_area_m2=v["min_area_m2"], skel=v["skel"], spur=v["spur"],
            reconnect=v["reconnect"],
            min_comp_len=v["min_comp_len"], keep_prob=v["keep_prob"],
            simplify_m=v["simplify_m"], smooth=v["smooth"],
        )

    def schedule(self):
        if not self.controls.get("auto").value:
            return
        if self._timer is not None:
            self._timer.cancel()
        self._timer = ui.timer(0.45, lambda: self.render(), once=True)

    async def render(self):
        if self.rendering:
            self.dirty = True
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
                        core.load, src, bool(v["use_drainage"]), scale)
                    self.loaded_sig = sig
                import time as _t
                t0 = _t.monotonic()
                self.stat.set_text("extracting roads…")
                gdf = await run.io_bound(core.extract, self.loaded, self.ucfg())
                png = await run.io_bound(core.render_png, self.loaded, gdf, v["background"])
                dt = _t.monotonic() - t0
                self.image.set_source(png)
                st = core.stats(gdf)
                self.stat.set_text(
                    f"{src.block} · {src.model}   —   {st['km']} km · "
                    f"{st['segments']} segments   ({dt:.1f}s @ "
                    f"{v['scale'].split()[0].lower()} res)")
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
            tag = datetime.now().strftime("%m%d_%H%M%S")
            res = await run.io_bound(core.export, gdf, src, self.ucfg(), tag)
            ui.notify(f"exported {res['segments']} segments · {res['km']} km\n"
                      f"{res['gpkg']}", type="positive", multi_line=True, timeout=9000)
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"export failed: {exc}", type="negative", multi_line=True)


def _model_options(block: str) -> list[str]:
    return [s.model for s in SOURCES.get(block, [])]


def _slider(store, key, label, lo, hi, step, default, compact=False):
    if label:
        ui.label(label).classes("text-xs text-gray-500 mt-1")
    sl = ui.slider(min=lo, max=hi, step=step, value=default).props(
        "label-always" if not compact else "label").classes(
        "flex-grow" if compact else "w-full")
    store[key] = sl
    return sl


def build_extract_tab(s: Studio):
    c = s.controls
    with ui.row().classes("w-full no-wrap gap-4"):
        with ui.column().classes("gap-3").style("width:380px; min-width:380px;"):
            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Source").classes("text-sm font-bold text-gray-600")
                    ui.button(icon="refresh", on_click=lambda: _rescan_extract(s)).props(
                        "flat dense round").tooltip("Rescan models (after a training run)")
                c["block"] = ui.select(
                    BLOCKS, value=("613590" if "613590" in BLOCKS else BLOCKS[0]),
                    label="Block").props("dense outlined").classes("w-full")
                c["model"] = ui.select(
                    _model_options(c["block"].value),
                    value=_model_options(c["block"].value)[0],
                    label="Model").props("dense outlined").classes("w-full")

                def _on_block(_):
                    opts = _model_options(c["block"].value)
                    c["model"].options = opts
                    c["model"].value = opts[0] if opts else None
                    c["model"].update(); s.schedule()

                c["block"].on_value_change(_on_block)
                with ui.row().classes("w-full gap-2 items-center"):
                    c["scale"] = ui.select(list(SCALE), value="Half",
                        label="Preview res").props("dense outlined").classes("flex-grow")
                    c["background"] = ui.select(["hillshade", "prob"], value="hillshade",
                        label="Backdrop").props("dense outlined").classes("flex-grow")
                c["use_drainage"] = ui.checkbox("Suppress drainage", value=True)

            with ui.card().classes("w-full"):
                ui.label("Extraction knobs").classes("text-sm font-bold text-gray-600")
                c["enhance"] = ui.select(["none", "sato", "frangi", "meijering", "blend"],
                    value="none", label="Ridge enhance").props("dense outlined").classes("w-full")
                c["thresh"] = ui.select(["global", "otsu", "hysteresis"], value="global",
                    label="Threshold mode").props("dense outlined").classes("w-full")
                glob_box = ui.column().classes("w-full gap-0")
                with glob_box:
                    _slider(c, "t", "Threshold (strip black below)", 0.05, 0.95, 0.05, 0.30)
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
                    c["pathopen"] = ui.checkbox("Path-open", value=False)
                    _slider(c, "po_len_m", "len m", 4, 40, 1, 14, compact=True)
                _slider(c, "min_area_m2", "Min blob area (m²)", 0, 400, 10, 10)
                c["skel"] = ui.select(["zhang", "lee", "medial"], value="lee",
                    label="Skeleton method").props("dense outlined").classes("w-full")
                _slider(c, "spur", "Prune spurs shorter than (m)", 0, 60, 2, 6)
                c["reconnect"] = ui.select(["none", "lcp", "mst"], value="none",
                    label="Reconnect gaps").props("dense outlined").classes("w-full")
                # Smart noise filter (connectivity + evidence): a segment is
                # dropped only if its whole network is BOTH short and faint.
                # DEFAULT 0 = OFF (keep every road — matches the raw faithful
                # trace). Slide up ONLY to clean speckle; keep_prob is the
                # brightness escape hatch so real faint roads aren't cut.
                _slider(c, "min_comp_len", "Filter: drop networks shorter than (m)", 0, 200, 5, 0)
                _slider(c, "keep_prob", "…unless mean road-prob ≥", 0.3, 0.9, 0.05, 0.45)

            with ui.card().classes("w-full"):
                ui.label("Polyline geometry").classes("text-sm font-bold text-gray-600")
                ui.label("Turns the raw pixel-staircase trace into clean, "
                         "editable QGIS polylines.").classes("text-xs text-gray-500")
                _slider(c, "simplify_m", "Simplify tolerance (m)", 0.0, 8.0, 0.5, 2.0)
                _slider(c, "smooth", "Smoothing passes", 0, 4, 1, 1)

            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center justify-between"):
                    c["auto"] = ui.switch("Auto-render", value=True)
                    ui.button("Render", icon="refresh", on_click=lambda: s.render()).props("color=primary")
                ui.button("Export layer for QGIS", icon="download",
                          on_click=lambda: s.export()).props("color=secondary outline").classes("w-full")

        with ui.column().classes("flex-grow gap-2"):
            with ui.row().classes("items-center gap-3"):
                s.spinner = ui.spinner(size="sm", color="primary")
                s.spinner.set_visibility(False)
                s.stat = ui.label("ready").classes("text-sm text-gray-600 font-mono")
            s.image = ui.image().classes("w-full rounded shadow").style(
                "background:#111; min-height:400px;")

    for name, w in c.items():
        if name in ("block", "thresh"):
            continue
        if hasattr(w, "on_value_change"):
            w.on_value_change(lambda _: s.schedule())
    hyst_box.set_visibility(False)
    return s


def _rescan_extract(s: Studio):
    rescan_sources()
    c = s.controls
    opts = _model_options(c["block"].value)
    c["model"].options = opts
    if c["model"].value not in opts and opts:
        c["model"].value = opts[0]
    c["model"].update()
    ui.notify(f"{sum(len(v) for v in SOURCES.values())} models across "
              f"{len(BLOCKS)} blocks", type="info")


# ===========================================================================
# Model Lab tab
# ===========================================================================
@dataclass
class Lab:
    controls: dict = field(default_factory=dict)
    run: object = None            # train.TrainRun
    progress: object = None
    status: object = None
    logbox: object = None
    plot: object = None
    train_btn: object = None
    stop_btn: object = None
    on_new_model: object = None   # callback to rescan Extract

    def ui_vals(self) -> dict:
        return {k: w.value for k, w in self.controls.items() if hasattr(w, "value")}

    def apply_preset(self, key: str):
        p = train.PRESETS[key]
        c = self.controls
        c["base"].value = p.get("base", key)
        c["res"].value = "1m" if p["res"] == "1m" else "0.5m"
        c["init"].value = p["init"]
        c["loss"].value = p["loss"]
        c["ep"].value = p["ep"]
        c["lr"].value = p["lr"]
        c["corr"].value = p["corr"]
        c["alpha_road"].value = p["alpha_road"]
        c["cldice_w"].value = p.get("cldice_w", 0.3)
        c["cldice_iters"].value = p.get("cldice_iters", 6)
        c["edge_w"].value = p.get("edge_w", 3.0)
        c["ori_w"].value = p.get("ori_w", 0.3)
        c["gamma"].value = p.get("gamma", 2.0)
        if not c["name"].value:
            c["name"].value = f"lab_{train.safe_name(key)}"
        self._refresh_loss_boxes()

    def _refresh_loss_boxes(self):
        loss = self.controls["loss"].value
        self._boxes["cldice"].set_visibility(loss == "cldice")
        self._boxes["boundary"].set_visibility(loss == "boundary")
        self._boxes["orient"].set_visibility(loss == "orient")
        self._boxes["focal"].set_visibility(loss == "focal")

    def start(self):
        if self.run and self.run.running():
            ui.notify("a run is already training", type="warning")
            return
        v = self.ui_vals()
        name = train.safe_name(v.get("name") or "custom")
        ui_cfg = dict(
            base=v["base"], res=("1m" if v["res"] == "1m" else "05"),
            init=v["init"], loss=v["loss"], ep=v["ep"], lr=v["lr"],
            corr=v["corr"], alpha_road=v["alpha_road"],
            cldice_w=v["cldice_w"], cldice_iters=v["cldice_iters"],
            edge_w=v["edge_w"], ori_w=v["ori_w"], gamma=v["gamma"])
        cfg = train.build_config(name, ui_cfg)
        self.run = train.launch(name, cfg)
        self.train_btn.disable(); self.stop_btn.enable()
        self.status.set_text(f"launched '{name}' — building datasets…")
        ui.notify(f"training '{name}' started (PID {self.run.proc.pid})", type="positive")

    def stop(self):
        if self.run and self.run.running():
            self.run.stop()
            ui.notify("stop signal sent", type="info")

    def poll(self):
        if not self.run:
            return
        pr = train.parse_progress(self.run.log_path)
        self.progress.set_value(pr["frac"])
        self.logbox.set_content("```\n" + pr["tail"] + "\n```")
        if pr["epoch"]:
            msg = (f"epoch {pr['epoch']}/{pr['total']} · "
                   f"tr_loss {pr['tr_loss']:.4f} · val IoU {pr['val_iou']:.4f}")
        else:
            msg = "starting… (dataset build + first epoch can take a few min)"
        rows = train.curve(self.run.out_dir)
        if rows:
            self._draw_curve(rows)
        alive = self.run.running()
        if not alive:
            rc = self.run.returncode()
            if pr["done"] or rc == 0:
                self.status.set_text(f"✓ done — '{self.run.name}' is now in Extract")
                if self.on_new_model:
                    self.on_new_model()
            else:
                self.status.set_text(f"✗ exited (code {rc}) — see log")
            self.train_btn.enable(); self.stop_btn.disable()
            self.run = None
        else:
            self.status.set_text(msg)

    def _draw_curve(self, rows):
        import plotly.graph_objects as go
        ep = [r["epoch"] for r in rows]
        fig = go.Figure()
        fig.add_scatter(x=ep, y=[r["val_iou"] for r in rows], name="val road IoU",
                        line=dict(color="#2f6f4f", width=2))
        fig.add_scatter(x=ep, y=[r["tr_loss"] for r in rows], name="train loss",
                        yaxis="y2", line=dict(color="#c0562f", width=1, dash="dot"))
        fig.update_layout(
            margin=dict(l=40, r=40, t=10, b=30), height=300,
            xaxis_title="epoch", yaxis=dict(title="val IoU"),
            yaxis2=dict(title="loss", overlaying="y", side="right"),
            legend=dict(orientation="h", y=1.15), showlegend=True)
        self.plot.update_figure(fig)


def build_lab_tab(lab: Lab, on_new_model):
    lab.on_new_model = on_new_model
    lab._boxes = {}
    c = lab.controls
    with ui.row().classes("w-full no-wrap gap-4"):
        with ui.column().classes("gap-3").style("width:380px; min-width:380px;"):
            with ui.card().classes("w-full"):
                ui.label("Recipe").classes("text-sm font-bold text-gray-600")
                preset = ui.select(list(train.PRESETS), value="cldice",
                    label="Start from preset").props("dense outlined").classes("w-full")
                ui.button("Load preset", icon="download",
                          on_click=lambda: lab.apply_preset(preset.value)).props(
                    "flat dense").classes("w-full")
                c["name"] = ui.input("Run name", placeholder="lab_cldice_w05").props(
                    "dense outlined").classes("w-full")
                c["base"] = ui.select(list(train.PRESETS), value="cldice",
                    label="Inherit defaults from").props("dense outlined").classes("w-full")

            with ui.card().classes("w-full"):
                ui.label("Architecture & data").classes("text-sm font-bold text-gray-600")
                with ui.row().classes("w-full gap-2"):
                    c["res"] = ui.select(["1m", "0.5m"], value="1m", label="Resolution").props(
                        "dense outlined").classes("flex-grow")
                    c["init"] = ui.select(["corrected", "scratch"], value="corrected",
                        label="Init").props("dense outlined").classes("flex-grow")
                c["corr"] = ui.checkbox("Include 613590 corrections", value=True)
                with ui.row().classes("w-full gap-2"):
                    c["ep"] = ui.number("Epochs", value=12, min=1, max=80, step=1).props(
                        "dense outlined").classes("flex-grow")
                    c["lr"] = ui.number("Learning rate", value=2e-4, format="%.5f",
                        step=1e-4).props("dense outlined").classes("flex-grow")

            with ui.card().classes("w-full"):
                ui.label("Loss").classes("text-sm font-bold text-gray-600")
                c["loss"] = ui.select(train.LOSSES, value="cldice", label="Objective").props(
                    "dense outlined").classes("w-full")
                _slider(c, "alpha_road", "Focal α (road weight)", 0.5, 0.9, 0.02, 0.72)
                lab._boxes["cldice"] = ui.column().classes("w-full gap-0")
                with lab._boxes["cldice"]:
                    _slider(c, "cldice_w", "clDice weight", 0.0, 1.0, 0.05, 0.30)
                    _slider(c, "cldice_iters", "clDice skeleton iters", 2, 12, 1, 6)
                lab._boxes["boundary"] = ui.column().classes("w-full gap-0")
                with lab._boxes["boundary"]:
                    _slider(c, "edge_w", "Road-edge weight", 1.0, 6.0, 0.5, 3.0)
                lab._boxes["orient"] = ui.column().classes("w-full gap-0")
                with lab._boxes["orient"]:
                    _slider(c, "ori_w", "Orientation head weight", 0.0, 1.0, 0.05, 0.30)
                lab._boxes["focal"] = ui.column().classes("w-full gap-0")
                with lab._boxes["focal"]:
                    _slider(c, "gamma", "Focal γ", 0.0, 4.0, 0.5, 2.0)
                c["loss"].on_value_change(lambda _: lab._refresh_loss_boxes())

            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center justify-between"):
                    lab.train_btn = ui.button("Train", icon="model_training",
                        on_click=lambda: lab.start()).props("color=primary")
                    lab.stop_btn = ui.button("Stop", icon="stop",
                        on_click=lambda: lab.stop()).props("color=negative outline")
                    lab.stop_btn.disable()
                ui.label("GPU is serialized — one run at a time. GTX 1070 Ti: "
                         "~1–4 min/epoch at 1 m.").classes("text-xs text-gray-500")

        with ui.column().classes("flex-grow gap-2"):
            lab.status = ui.label("configure a recipe and press Train").classes(
                "text-sm text-gray-700 font-mono")
            lab.progress = ui.linear_progress(value=0.0, show_value=False).classes("w-full")
            lab.plot = ui.plotly({}).classes("w-full").style("height:300px")
            ui.label("live log").classes("text-xs text-gray-500 mt-2")
            lab.logbox = ui.markdown("```\n(no run yet)\n```").classes(
                "w-full").style("font-size:11px; max-height:260px; overflow:auto;")

    lab.apply_preset("cldice")
    ui.timer(2.0, lambda: lab.poll())
    return lab


# ===========================================================================
# page
# ===========================================================================
def build():
    @ui.page("/")
    def page():
        ui.query("body").style("background:#f4f6f8;")
        with ui.header().classes("items-center justify-between px-4 py-2").style("background:#2f6f4f;"):
            ui.label("Roads Studio").classes("text-xl font-semibold text-white")
            ui.label("tune extraction · train models").classes("text-sm text-white/80")

        s = Studio()
        lab = Lab()
        with ui.tabs().classes("w-full") as tabs:
            t_extract = ui.tab("Extract", icon="tune")
            t_lab = ui.tab("Model Lab", icon="science")
        with ui.tab_panels(tabs, value=t_extract).classes("w-full p-4"):
            with ui.tab_panel(t_extract):
                build_extract_tab(s)
            with ui.tab_panel(t_lab):
                build_lab_tab(lab, on_new_model=lambda: _rescan_extract(s))

        ui.timer(0.3, lambda: s.render(), once=True)
