"""Risk-ranking core for 5.3. Library, not a script.

Purpose
    Pure functions behind fw_5_3 stages S1 to S7, so every stage script and the bootstrap use the same code.
    - build_sites(): documented records (P = 1) plus candidates (P = K-rank tercile band, never a probability)
    - receptor arrays and exposure(): nearest distance and counts or presence within distance bands
    - hazard(): H components from records and priors only, 1800 sentinel kept as its own class
    - check_lineage(): fails when any endpoint column or endpoint input reaches H, E or P
    - rank-scaled indices (mid-rank, missing components under a declared IndexRule), check_index(),
      scenarios A to E with competition ranks (ties stay ties, missing keys are unrankable), weighted-sum variant
    - top_n(), jaccard(), kendall_tau()
    - enrichment() and the endpoint event rule
    - banned_phrase_hits() for written outputs
    Three quantities stay separate in every table. A ranking is a scenario product, not evidence about wells.

Inputs / outputs
    None by itself. GeoDataFrames and arrays in, DataFrames and dicts out.
Run
    Not runnable. Tested by expansions/5_tasks/5_3_risk_ranking/src/test_5_3.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import kendalltau, rankdata

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

P_BAND_VALUE = {"record": 1.0, "K1": 0.75, "K2": 0.5, "K3": 0.25, "below_K": 0.0}
SCENARIOS = ("A", "B", "C", "D")


# ----------------------------------------------------------------------------- sites
def top_n_size(n_eligible: int, n_max: int = 50, share: float = 0.05) -> int:
    """N = min(n_max, share of eligible sites), at least 1."""
    return max(1, min(int(n_max), int(np.ceil(share * n_eligible))))


def p_bands(scores: np.ndarray, k: int, cuts=None):
    """K-rank tercile band per candidate. Candidates ranked by score. Top K split into terciles K1 to K3.
    cuts = (c1, c2, c3) score cut points; when None they come from the top-K scores themselves.
    Returns (bands, cuts). A band is ordinal. It is P(feature), never P(well)."""
    s = np.asarray(scores, float)
    if cuts is None:
        top = np.sort(s)[::-1][:max(k, 1)]
        if len(top) == 0:
            return np.array([], dtype=object), (np.inf, np.inf, np.inf)
        c1, c2 = np.quantile(top, [2 / 3, 1 / 3])
        c3 = top.min()
        cuts = (float(c1), float(c2), float(c3))
    c1, c2, c3 = cuts
    b = np.where(s >= c1, "K1", np.where(s >= c2, "K2", np.where(s >= c3, "K3", "below_K")))
    return b.astype(object), cuts


def build_sites(records, candidates, k: int, assoc_radius: float, cuts=None):
    """One row per site. Records keep P = 1 (p_source 'record'). EVERY candidate within assoc_radius of a
    record is merged into its nearest record site as surface evidence (a proposed association, flagged).
    Review 2026-11-06: the old rule merged only each record's single nearest candidate, so a second candidate
    beside the same record became its own undocumented site. Other candidates are their own sites with a P band.
    records     DataFrame with site keys PERMIT_NUM, x, y, WELL_STATU (+ date fields)
    candidates  DataFrame with cand_id, score, x, y, block_id
    Record columns added: surface_evidence (0/1), assoc_cand_id (nearest merged candidate, -1 if none),
    n_assoc_cand (how many candidates merged into this record)."""
    rec = records.copy().reset_index(drop=True)
    cand = candidates.copy().reset_index(drop=True)
    bands, cuts = p_bands(cand["score"].to_numpy(), k, cuts)
    cand["p_band"] = bands
    rec["surface_evidence"] = 0
    rec["assoc_cand_id"] = -1
    rec["n_assoc_cand"] = 0
    if len(rec) and len(cand):
        d, j = cKDTree(rec[["x", "y"]].to_numpy()).query(cand[["x", "y"]].to_numpy())
        hit = d <= assoc_radius
        cid = cand["cand_id"].to_numpy()
        for r_i in np.unique(j[hit]):
            mine = np.flatnonzero(hit & (j == r_i))
            rec.loc[r_i, "surface_evidence"] = 1
            rec.loc[r_i, "n_assoc_cand"] = len(mine)
            rec.loc[r_i, "assoc_cand_id"] = int(cid[mine[np.argmin(d[mine])]])
        cand = cand[~hit]
    r = pd.DataFrame({
        "site_id": "rec_" + rec["PERMIT_NUM"].astype(str), "x": rec["x"].to_numpy(), "y": rec["y"].to_numpy(),
        "p_source": "record", "p_band": "record", "status": rec["WELL_STATU"].to_numpy(),
        "surface_evidence": rec["surface_evidence"].to_numpy(), "assoc_cand_id": rec["assoc_cand_id"].to_numpy(),
        "n_assoc_cand": rec["n_assoc_cand"].to_numpy(), "cand_score": np.nan, "block_id": rec.get("block_id", pd.Series(-1, index=rec.index)).to_numpy(),
        "conditional": ""})
    for c in ("SPUD_DATE", "DATE_PLUGG", "PERMIT_DAT"):
        if c in rec:
            r[c] = rec[c].astype(str).to_numpy()
    c = pd.DataFrame({
        "site_id": "cand_" + cand["cand_id"].astype(int).astype(str), "x": cand["x"].to_numpy(),
        "y": cand["y"].to_numpy(), "p_source": "feature_band", "p_band": cand["p_band"].to_numpy(),
        "status": "_undocumented_candidate", "surface_evidence": 1, "assoc_cand_id": cand["cand_id"].to_numpy(),
        "n_assoc_cand": 0, "cand_score": cand["score"].to_numpy(), "block_id": cand.get("block_id", pd.Series(-1, index=cand.index)).to_numpy(),
        "conditional": th.CONDITIONAL})
    sites = pd.concat([r, c], ignore_index=True)
    sites["P"] = sites["p_band"].map(P_BAND_VALUE).astype(float)
    th.ek.assert_unique(sites, "site_id")
    return sites, cuts


# ----------------------------------------------------------------------------- receptors and exposure
def densify_xy(geoms, step: float = 5.0) -> np.ndarray:
    """Lines or polygon boundaries to points every `step` m, so distances are one KD-tree query."""
    import shapely
    out = []
    for g in geoms:
        if g is None or g.is_empty:
            continue
        line = g.boundary if g.geom_type in ("Polygon", "MultiPolygon") else g
        L = line.length
        if L == 0:
            out.append(np.array(shapely.get_coordinates(g))[:, :2])
            continue
        ds = np.arange(0, L + step, step)
        pts = shapely.line_interpolate_point(line, np.minimum(ds, L)) if line.geom_type == "LineString" else \
            [line.interpolate(d) for d in np.minimum(ds, L)]
        out.append(np.array(shapely.get_coordinates(np.asarray(pts, dtype=object)))[:, :2])
    return np.vstack(out) if out else np.empty((0, 2))


class Receptor:
    """One receptor class prepared for fast repeated exposure queries (needed by the S5 bootstrap)."""

    def __init__(self, name: str, kind: str, gdf, pos_error_col: str | None = None, step: float = 5.0):
        self.name, self.kind = name, kind
        self.n = len(gdf)
        if kind == "points":
            geo = gdf.geometry
            if len(geo) and geo.geom_type.iloc[0] != "Point":
                geo = geo.centroid
            self.xy = np.c_[geo.x.to_numpy(), geo.y.to_numpy()] if len(geo) else np.empty((0, 2))
            self.err = (gdf[pos_error_col].fillna(0).to_numpy(float) if pos_error_col and pos_error_col in gdf
                        else np.zeros(len(self.xy)))
        elif kind in ("lines", "polygons"):
            self.xy = densify_xy(gdf.geometry.values, step)
            self.err = np.zeros(len(self.xy))
            self.polys = gdf.geometry.values if kind == "polygons" else None
        else:
            raise ValueError(kind)
        self.tree = cKDTree(self.xy) if len(self.xy) else None

    def exposure(self, site_xy: np.ndarray, bands) -> dict:
        n = len(site_xy)
        out = {}
        if self.tree is None:
            out[f"{self.name}_d_nearest"] = np.full(n, np.inf)
        else:
            d, _ = self.tree.query(site_xy)
            if self.kind == "polygons":
                import shapely
                inside = np.zeros(n, bool)
                for p in self.polys:
                    inside |= shapely.contains_xy(p, site_xy[:, 0], site_xy[:, 1])
                d = np.where(inside, 0.0, d)
                out[f"{self.name}_inside"] = inside.astype(int)
            out[f"{self.name}_d_nearest"] = d
        for b in bands:
            if self.kind == "points" and self.tree is not None:
                # error buffer: a receptor counts when its stated error could put it inside the band
                rmax = b + (self.err.max() if len(self.err) else 0)
                cnt = np.zeros(n, int)
                cnt_strict = np.zeros(n, int)
                for i, nb in enumerate(self.tree.query_ball_point(site_xy, rmax)):
                    if nb:
                        dd = np.hypot(*(self.xy[nb] - site_xy[i]).T)
                        cnt[i] = int((dd - self.err[nb] <= b).sum())
                        cnt_strict[i] = int((dd <= b).sum())
                out[f"{self.name}_n_{b}"] = cnt
                out[f"{self.name}_n_{b}_strict"] = cnt_strict
            else:
                out[f"{self.name}_n_{b}"] = (out[f"{self.name}_d_nearest"] <= b).astype(int)
        return out


def exposure_table(site_xy: np.ndarray, receptors: dict, bands) -> pd.DataFrame:
    cols = {}
    for r in receptors.values():
        cols.update(r.exposure(site_xy, bands))
    return pd.DataFrame(cols)


def e_component_columns(e_components: dict, present: set) -> dict:
    """Map receptor -> exposure column, keeping only receptors that are present. Direction +1 for counts and
    inside flags (more is more exposed), -1 for distances (closer is more exposed)."""
    out = {}
    for name, comp in e_components.items():
        if name not in present:
            continue
        col = f"{name}_{comp}"
        out[col] = -1 if comp.startswith("d_") else 1
    return out


def rank01(v: np.ndarray, direction: int = 1) -> np.ndarray:
    """Mid-rank percentile in (0, 1) with average ties: (rank - 0.5) / n. NaN stays NaN. direction -1 reverses.
    Review 2026-11-06 (rank01 extremes). The old (rank - 1) / (n - 1) mapped the lowest site to exactly 0, so
    in the scenario D product one component at its minimum zeroed the whole product whatever the others were.
    Mid-ranks never reach 0 or 1. A single finite value, or all values tied, gives 0.5."""
    v = np.asarray(v, float)
    out = np.full(len(v), np.nan)
    ok = np.isfinite(v)
    n = int(ok.sum())
    if n == 0:
        return out
    out[ok] = (rankdata(direction * v[ok]) - 0.5) / n
    return out


class IndexRule(dict):
    """How an index treats a missing component. Declared in config and stamped into outputs.
    rule          'unrankable' (default) or 'impute'
    min_coverage  share of components a site must have. Below it the index is NaN (unrankable). Default 1.0,
                  so no component is ever skipped silently
    impute        {column: raw value} used before ranking when rule is 'impute'. Every column with a missing
                  value must have a declared value, else the build fails"""

    def __init__(self, rule: str = "unrankable", min_coverage: float = 1.0, impute: dict | None = None):
        if rule not in ("unrankable", "impute"):
            raise ValueError(f"unknown missing-component rule {rule!r}")
        if not 0 < float(min_coverage) <= 1:
            raise ValueError("min_coverage must be in (0, 1]")
        super().__init__(rule=rule, min_coverage=float(min_coverage), impute=dict(impute or {}))

    @classmethod
    def from_cfg(cls, d: dict | None):
        d = d or {}
        return cls(d.get("rule", "unrankable"), d.get("min_coverage", 1.0), d.get("impute"))


def index_from(df: pd.DataFrame, cols: dict, rule: IndexRule | None = None) -> np.ndarray:
    """Mean of rank01 components. Review 5.3-01: a missing component is never skipped silently.
    Under the default rule a site missing any component gets NaN (unrankable). Under 'impute' the declared raw
    value fills the gap before ranking. min_coverage < 1 is an explicit, declared partial average."""
    rule = rule if rule is not None else IndexRule()
    if not cols:
        return np.full(len(df), np.nan)
    raw = {}
    for c in cols:
        v = df[c].replace([np.inf, -np.inf], np.nan).to_numpy(float).copy()
        miss = ~np.isfinite(v)
        if rule["rule"] == "impute" and miss.any():
            if c not in rule["impute"]:
                raise ValueError(f"index component {c} has {int(miss.sum())} missing values and no declared "
                                 "imputation value (IndexRule.impute)")
            v[miss] = float(rule["impute"][c])
        raw[c] = v
    M = np.column_stack([rank01(raw[c], s) for c, s in cols.items()])
    fin = np.isfinite(M)
    cov = fin.mean(1)
    mean = np.where(fin, M, 0.0).sum(1) / np.maximum(fin.sum(1), 1)
    return np.where(cov >= rule["min_coverage"] - 1e-12, mean, np.nan)


def coverage(df: pd.DataFrame, cols) -> np.ndarray:
    """Share of the listed components each site has (finite)."""
    cols = list(cols)
    if not cols:
        return np.zeros(len(df))
    return np.column_stack([np.isfinite(df[c].replace([np.inf, -np.inf], np.nan).to_numpy(float))
                            for c in cols]).mean(1)


class IndexUnusable(ValueError):
    """An index cannot rank sites (too few components or too few distinct values)."""


def check_index(values: np.ndarray, n_components: int, min_components: int, min_distinct: int, label: str):
    """Review 5.3-02. Raise IndexUnusable when an index has fewer than min_components components or fewer than
    min_distinct distinct finite values (it could not order a top N without ties deciding it)."""
    if n_components < min_components:
        raise IndexUnusable(f"{label} has {n_components} component(s), fewer than the declared minimum "
                            f"{min_components}")
    v = np.asarray(values, float)
    nd = int(len(np.unique(v[np.isfinite(v)])))
    if nd < min_distinct:
        raise IndexUnusable(f"{label} has {nd} distinct value(s), fewer than the declared minimum {min_distinct}")


# ----------------------------------------------------------------------------- hazard
def year_of(s) -> float:
    try:
        return float(str(s)[:4])
    except (TypeError, ValueError):
        return float("nan")


def age_bracket(spud: pd.Series, sentinels) -> np.ndarray:
    out = []
    for v in spud.astype(str):
        if v[:10] in sentinels:
            out.append("unknown_sentinel")
            continue
        y = year_of(v)
        if not np.isfinite(y) or y < 1859 or y > 2100:
            out.append("missing")
        elif y < 1956:
            out.append("pre1956")
        elif y < 1985:
            out.append("1956_1984")
        else:
            out.append("1985_on")
    return np.array(out, dtype=object)


def hazard(sites: pd.DataFrame, cfg: dict, extra_records: pd.DataFrame | None = None):
    """H components from records and priors only (fw_5_3 S2). Returns (table, lineage, dropped).
    Never reads an endpoint. Optional depth/formation columns enter only if their missing share is at most
    cfg['max_missing_share_for_h']."""
    H = pd.DataFrame({"site_id": sites["site_id"].to_numpy()})
    lineage = {}
    sh = cfg["status_hazard_score"]
    H["h_status"] = [sh.get(s, sh.get("_other", 1)) for s in sites["status"]]
    lineage["h_status"] = ["dep_wells:WELL_STATU", "config:status_hazard_score"]
    spud = sites["SPUD_DATE"] if "SPUD_DATE" in sites else pd.Series([""] * len(sites))
    br = age_bracket(spud, set(cfg["sentinel_dates"]))
    br = np.where(sites["p_source"].to_numpy() == "record", br, "missing")
    H["age_bracket"] = br
    H["h_age"] = [cfg["age_bracket_score"][b] for b in br]
    lineage["h_age"] = ["dep_wells:SPUD_DATE", "config:age_bracket_score"]
    plug = sites["DATE_PLUGG"] if "DATE_PLUGG" in sites else pd.Series([None] * len(sites))
    has_plug = plug.astype(str).str.match(r"^\d{4}").to_numpy()
    H["h_no_plug_record"] = np.where(sites["p_source"] == "record", (~has_plug).astype(float), np.nan)
    lineage["h_no_plug_record"] = ["dep_wells:DATE_PLUGG"]
    H["surface_evidence_flag"] = sites["surface_evidence"].to_numpy()   # level (a), kept as a separate flag
    lineage["surface_evidence_flag"] = ["candidates:score", "config:assoc_radius_m"]
    dropped = {}
    if extra_records is not None:
        for name, col in cfg.get("optional_hazard_columns", {}).items():
            if col not in extra_records:
                dropped[name] = "absent"
                continue
            v = extra_records[col]
            miss = float(v.isna().mean()) if len(v) else 1.0
            if miss > cfg["max_missing_share_for_h"]:
                dropped[name] = f"missing share {miss:.2f}"
                continue
            m = dict(zip("rec_" + extra_records["PERMIT_NUM"].astype(str), v))
            H[f"h_{name}"] = [m.get(s, np.nan) for s in sites["site_id"]]
            lineage[f"h_{name}"] = [f"dep_wells:{col}"]
    return H, lineage, dropped


def h_columns(H: pd.DataFrame, drop=()) -> dict:
    return {c: 1 for c in H.columns if c.startswith("h_") and c not in drop and pd.api.types.is_numeric_dtype(H[c])}


def h_index(H: pd.DataFrame, rule: IndexRule | None = None) -> np.ndarray:
    return index_from(H, h_columns(H), rule)


def check_lineage(lineage: dict, endpoint_columns, endpoint_inputs) -> None:
    """Endpoint isolation (fw_5_3 QC 3). Fails when any H, E or P column is an endpoint column or is derived
    from an endpoint input."""
    bad = []
    ec, ei = set(endpoint_columns), set(endpoint_inputs)
    for col, srcs in lineage.items():
        if col in ec:
            bad.append((col, "is an endpoint column"))
        for s in srcs:
            src, _, field = str(s).partition(":")
            if src in ei or field in ec:
                bad.append((col, s))
    if bad:
        raise AssertionError(f"ENDPOINT LEAK into H/E/P: {bad}")


# ----------------------------------------------------------------------------- scenarios
def _lex_rank(keys) -> np.ndarray:
    """Competition rank (1 = first, ties share the lowest rank, the next rank skips). keys is a list of arrays,
    most important first, larger = earlier. Review 2026-11-06: ties are never broken by row order. A site with a
    NaN in any key is unrankable and gets NaN. Returns a float array."""
    arrs = [np.asarray(k, float) for k in keys]
    n = len(arrs[0]) if arrs else 0
    out = np.full(n, np.nan)
    ok = np.ones(n, bool)
    for a in arrs:
        ok &= np.isfinite(a)
    idx = np.flatnonzero(ok)
    if not len(idx):
        return out
    K = np.column_stack([a[idx] for a in arrs])
    order = np.lexsort([-K[:, c] for c in range(K.shape[1] - 1, -1, -1)])
    Ks = K[order]
    new = np.r_[True, np.any(Ks[1:] != Ks[:-1], axis=1)]
    pos = np.arange(1, len(order) + 1)
    first = np.maximum.accumulate(np.where(new, pos, 0))
    out[idx[order]] = first
    return out


def tie_size(rank: np.ndarray) -> np.ndarray:
    """How many sites share each site's rank (1 = no tie). NaN for unrankable sites."""
    r = np.asarray(rank, float)
    out = np.full(len(r), np.nan)
    ok = np.isfinite(r)
    if ok.any():
        _, inv, cnt = np.unique(r[ok], return_inverse=True, return_counts=True)
        out[ok] = cnt[inv]
    return out


def _secondary(keys):
    """Keep the first key. Drop a later key only when it is NaN for every site (the component is absent
    everywhere, so it cannot break any tie and ties stay ties). A later key missing for some sites only makes
    those sites unrankable."""
    out = [keys[0]]
    for k in keys[1:]:
        if np.isfinite(np.asarray(k, float)).any():
            out.append(k)
    return out


def scenario_ranks(df: pd.DataFrame, agency_rank=None) -> pd.DataFrame:
    """Scenarios as rules, not findings. df needs P, H, E.
    A exposure first, ties by H. B hazard first, ties by E. C documented first, then E.
    D product of rank-scaled P, H, E (conditional on the feature model, never primary).
    E agency default, when supplied. Equal keys give equal ranks (reported as ties, see tie_size).
    A site with a missing primary key is unrankable (NaN rank)."""
    P, H, E = (df[c].to_numpy(float) for c in ("P", "H", "E"))
    rec = (df["p_source"].to_numpy() == "record").astype(float)
    out = pd.DataFrame(index=df.index)
    out["rank_A"] = _lex_rank(_secondary([E, H]))
    out["rank_B"] = _lex_rank(_secondary([H, E]))
    out["rank_C"] = _lex_rank(_secondary([rec, E]))
    prod = rank01(P) * rank01(H) * rank01(E)
    out["rank_D"] = _lex_rank([prod])
    if agency_rank is not None:
        a = np.asarray(agency_rank, float)
        out["rank_E"] = _lex_rank([-a])
    return out


def weighted_rank(df: pd.DataFrame, w) -> np.ndarray:
    """Weighted-sum variant. w = (wP, wH, wE) summing to 1, on rank-scaled components. A component with weight
    0 is not used. A site missing a used component is unrankable (review 5.3-01, never filled with 0)."""
    s = np.zeros(len(df))
    for wi, c in zip(w, ("P", "H", "E")):
        if wi > 0:
            s = s + wi * rank01(df[c].to_numpy(float))
    return _lex_rank([s])


def weight_grid(step: float = 0.1):
    """Each weight swept 0..1. The other two share the remainder equally, so the sum stays 1."""
    vals = np.round(np.arange(0, 1 + 1e-9, step), 6)
    rows = []
    for i, name in enumerate(("P", "H", "E")):
        for v in vals:
            w = np.full(3, (1 - v) / 2)
            w[i] = v
            rows.append((name, float(v), tuple(float(x) for x in w)))
    return rows


def top_set(rank: np.ndarray, n: int, ids) -> set:
    """Sites ranked n or better. With ties at the cutoff the set holds more than n sites (ties are kept,
    never cut by row order). Unrankable sites (NaN) are never in it."""
    ids = np.asarray(ids)
    r = np.asarray(rank, float)
    return set(ids[np.isfinite(r) & (r <= n)])


def jaccard(a: set, b: set) -> float:
    """NaN when both sets are empty (nothing was rankable), never a perfect 1.0."""
    return len(a & b) / len(a | b) if (a or b) else float("nan")


def kendall_tau(r1, r2) -> float:
    t = kendalltau(r1, r2, nan_policy="omit").statistic
    return float(t) if np.isfinite(t) else float("nan")


# ----------------------------------------------------------------------------- endpoint
def endpoint_events(flux: np.ndarray, rule: dict) -> np.ndarray:
    """Event = measured rate at or above the cutoff, or the top decile of measured rates."""
    return endpoint_events_rule(flux, rule)[0]


def endpoint_events_rule(flux: np.ndarray, rule: dict):
    """Returns (events, rule_used). kind 'top_decile', or 'rate_cutoff' with flux_cutoff_kg_h. When the cutoff
    is absent and top_decile_fallback is true the top decile is used (review 2026-11-06: the fallback key was
    never read). An absent cutoff without the fallback, or an unknown kind, raises."""
    f = np.asarray(flux, float)
    kind = rule.get("kind")
    if kind == "top_decile":
        return f >= np.nanquantile(f, 0.9), "top_decile"
    if kind != "rate_cutoff":
        raise ValueError(f"unknown endpoint event rule kind {kind!r}")
    cut = rule.get("flux_cutoff_kg_h")
    if cut is None:
        if rule.get("top_decile_fallback"):
            return f >= np.nanquantile(f, 0.9), "top_decile (fallback, no cutoff given)"
        raise ValueError("endpoint rule rate_cutoff has no flux_cutoff_kg_h and no top_decile_fallback")
    return f >= float(cut), f"rate_cutoff {float(cut)} kg/h"


def enrichment(rank: np.ndarray, event: np.ndarray, n: int, weight=None) -> float:
    """Events in the top n over events expected in a random n. Inverse inclusion weights optional."""
    rank, event = np.asarray(rank), np.asarray(event, bool)
    w = np.ones(len(rank)) if weight is None else np.asarray(weight, float)
    top = rank <= n
    tot = (w * event).sum()
    if tot == 0 or top.sum() == 0:
        return float("nan")
    return float((w * event)[top].sum() / (tot * (w[top].sum() / w.sum())))


# ----------------------------------------------------------------------------- outputs
def banned_phrase_hits(text: str, phrases, alone) -> list:
    """Banned phrases in written outputs (fw_5_3 QC 9). 'risk score' is allowed only as 'risk score
    scenario'-style compounds, never alone."""
    low = text.lower()
    hits = [p for p in phrases if p.lower() in low]
    for p in alone:
        for m in re.finditer(re.escape(p.lower()), low):
            tail = low[m.end():m.end() + 10]
            if not tail.strip().startswith(("scenario", "component")):
                hits.append(p)
                break
    return hits
