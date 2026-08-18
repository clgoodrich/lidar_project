"""Well age vs pad/pit morphology — does surface geometry encode drilling era?

Question: PA DEP spud dates are missing (sentinel 1800-01-01) for 92% of the
orphan list. Can pad/pit morphology from the hand annotations recover an era
signal, calibrated on the wells that DO have real dates?

Method:
  1. Load venango_wells_all.gpkg; classify SPUD_DATE into real / sentinel_1800
     / missing; reproject to EPSG:6346 (annotation CRS).
  2. Load hand-annotated pads (pad.shp, repo-wide) + pits (pit_inside.shp).
  3. Match each well to nearest pad and nearest pit within MATCH_M (50 m,
     the literature default for PA DEP historic positional uncertainty —
     see docs/02_data_dictionary_wells.md note 2).
  4. Per matched pad: area, perimeter, compactness 4*pi*A/P^2, elongation
     (min rotated rect aspect), n wells sharing the pad. Per well: has_pit,
     has_pad flags.
  5. Stats: Spearman rho of each feature vs spud year (real-dated wells);
     Kruskal-Wallis across era bins; and the deployment-relevant contrast —
     dated-modern vs sentinel-historic morphology (Mann-Whitney U).

Outputs (OUT_DIR):
  well_pad_matches.csv     one row per well with morphology + era class
  summary_stats.json       all test statistics
  fig_morph_by_era.png     boxplots of features by era bin
  fig_pit_pad_rates.png    pit/pad match rates by spud class

Reproduce: python notebooks/wellsight_v2/s7_analysis/_well_age_morphology.py
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
WELLS = path_for("derivatives") / "venango_wells_all.gpkg"
PADS = path_for("truth") / "pad.shp"
PITS = path_for("truth") / "pit_inside.shp"
OUT_DIR = path_for("experiments") / "well_age_morphology"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:6346"
MATCH_M = 50.0

ERA_BINS = [(-np.inf, 1956, "pre-1956"), (1956, 1980, "1956-1979"),
            (1980, 2000, "1980-1999"), (2000, np.inf, "2000+")]


def era_of(year):
    for lo, hi, name in ERA_BINS:
        if lo <= year < hi:
            return name
    return None


def pad_morphology(g):
    """Area, perimeter, compactness, elongation for one (multi)polygon."""
    if g is None or g.is_empty:
        return np.nan, np.nan, np.nan, np.nan
    area = g.area
    per = g.length
    compact = 4 * np.pi * area / per**2 if per > 0 else np.nan
    rect = g.minimum_rotated_rectangle
    if rect.geom_type != "Polygon":
        return area, per, compact, np.nan
    xs, ys = rect.exterior.coords.xy
    e1 = np.hypot(xs[1] - xs[0], ys[1] - ys[0])
    e2 = np.hypot(xs[2] - xs[1], ys[2] - ys[1])
    major, minor = max(e1, e2), min(e1, e2)
    elong = minor / major if major > 0 else np.nan
    return area, per, compact, elong


def main():
    wells = gpd.read_file(WELLS).to_crs(CRS)
    sd = pd.to_datetime(wells["SPUD_DATE"], errors="coerce")
    wells["spud_year"] = sd.dt.year
    wells["spud_class"] = "missing"
    wells.loc[wells["spud_year"].notna(), "spud_class"] = "real"
    wells.loc[wells["spud_year"] == 1800, "spud_class"] = "sentinel_1800"
    wells["era"] = wells["spud_year"].where(wells["spud_class"] == "real").map(
        lambda y: era_of(y) if pd.notna(y) else None)

    pads = gpd.read_file(PADS).to_crs(CRS).reset_index(names="pad_idx")
    pits = gpd.read_file(PITS).to_crs(CRS).reset_index(names="pit_idx")
    pads.geometry = pads.geometry.make_valid()
    pits.geometry = pits.geometry.make_valid()
    pads = pads[pads.geometry.notna() & ~pads.geometry.is_empty].copy()
    pits = pits[pits.geometry.notna() & ~pits.geometry.is_empty].copy()
    print(f"wells {len(wells)} | pads {len(pads)} | pits {len(pits)}")

    # restrict wells to the annotated neighborhood: within MATCH_M of any pad
    # OR pit — everything else has no annotation to compare against, and
    # counting it as "no pad" would conflate era with annotation coverage.
    # Coverage flag: well within 200 m of any annotation = "annotated area".
    ann = gpd.GeoDataFrame(
        geometry=pd.concat([pads.geometry, pits.geometry],
                           ignore_index=True), crs=CRS)
    jall = gpd.sjoin_nearest(wells[["geometry"]], ann, how="left",
                             distance_col="d_any_annotation")
    jall = jall[~jall.index.duplicated(keep="first")]
    wells["d_any_annotation"] = jall["d_any_annotation"]
    in_area = wells[wells["d_any_annotation"] <= 200].copy()
    print(f"wells within 200 m of any annotation: {len(in_area)}")

    m = pd.DataFrame(index=in_area.index)
    morph = pads.geometry.apply(pad_morphology)
    pads[["area_m2c", "perim_m", "compactness", "elongation"]] = (
        pd.DataFrame(morph.tolist(), index=pads.index))

    jp = gpd.sjoin_nearest(in_area, pads[["pad_idx", "area_m2c", "perim_m",
                                          "compactness", "elongation",
                                          "geometry"]],
                           how="left", max_distance=MATCH_M,
                           distance_col="d_pad")
    jp = jp[~jp.index.duplicated(keep="first")]
    ji = gpd.sjoin_nearest(in_area, pits[["pit_idx", "geometry"]], how="left",
                           max_distance=MATCH_M, distance_col="d_pit")
    ji = ji[~ji.index.duplicated(keep="first")]

    df = in_area[["PERMIT_NUM", "WELL_STATU", "spud_year", "spud_class",
                  "era", "d_any_annotation"]].copy()
    for c in ["pad_idx", "area_m2c", "perim_m", "compactness", "elongation",
              "d_pad"]:
        df[c] = jp[c]
    df["pit_idx"] = ji["pit_idx"]
    df["d_pit"] = ji["d_pit"]
    df["has_pad"] = df["pad_idx"].notna()
    df["has_pit"] = df["pit_idx"].notna()
    # wells per pad (multi-well pads are a modern signature)
    wpp = df.groupby("pad_idx").size().rename("wells_on_pad")
    df = df.join(wpp, on="pad_idx")
    df.to_csv(OUT_DIR / "well_pad_matches.csv", index=False)

    # ---------------- statistics ----------------
    out = {"n_wells_in_area": int(len(df)),
           "match_radius_m": MATCH_M,
           "counts_by_class": df["spud_class"].value_counts().to_dict()}

    real = df[(df["spud_class"] == "real") & df["has_pad"]]
    feats = ["area_m2c", "perim_m", "compactness", "elongation",
             "wells_on_pad"]
    out["spearman_vs_spud_year"] = {}
    for f in feats:
        v = real[[f, "spud_year"]].dropna()
        if len(v) >= 10:
            rho, p = stats.spearmanr(v[f], v["spud_year"])
            out["spearman_vs_spud_year"][f] = {
                "rho": round(float(rho), 3), "p": float(p), "n": len(v)}

    out["kruskal_by_era"] = {}
    era_groups = {e: real[real["era"] == e] for _, _, e in ERA_BINS}
    era_groups = {e: g for e, g in era_groups.items() if len(g) >= 5}
    out["era_n"] = {e: int(len(g)) for e, g in era_groups.items()}
    for f in feats:
        samples = [g[f].dropna() for g in era_groups.values()]
        samples = [s for s in samples if len(s) >= 5]
        if len(samples) >= 2:
            h, p = stats.kruskal(*samples)
            out["kruskal_by_era"][f] = {"H": round(float(h), 2),
                                        "p": float(p)}

    # dated-modern vs sentinel-historic (the deployment question)
    mod = df[(df["spud_class"] == "real") & df["has_pad"]]
    hist = df[(df["spud_class"] == "sentinel_1800") & df["has_pad"]]
    out["modern_vs_sentinel"] = {"n_modern": int(len(mod)),
                                 "n_sentinel": int(len(hist))}
    for f in feats:
        a, b = mod[f].dropna(), hist[f].dropna()
        if len(a) >= 10 and len(b) >= 10:
            u, p = stats.mannwhitneyu(a, b)
            out["modern_vs_sentinel"][f] = {
                "median_modern": round(float(a.median()), 3),
                "median_sentinel": round(float(b.median()), 3),
                "p": float(p)}
    for flag in ["has_pad", "has_pit"]:
        a = df[df["spud_class"] == "real"][flag]
        b = df[df["spud_class"] == "sentinel_1800"][flag]
        tab = [[int(a.sum()), int((~a).sum())],
               [int(b.sum()), int((~b).sum())]]
        if min(len(a), len(b)) >= 10:
            _, p = stats.fisher_exact(tab)
            out["modern_vs_sentinel"][flag] = {
                "rate_modern": round(float(a.mean()), 3),
                "rate_sentinel": round(float(b.mean()), 3), "p": float(p)}

    # can morphology BIN wells? cross-validated 2-era classifier
    # (1956-1979 vs 1980-1999; 2000+ dropped, n too small)
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_score

    clf_df = real[real["era"].isin(["1956-1979", "1980-1999"])].copy()
    clf_df["has_pit_f"] = clf_df["has_pit"].astype(float)
    X_cols = feats + ["has_pit_f"]
    Xy = clf_df[X_cols + ["era"]].dropna()
    if len(Xy) >= 50:
        X = Xy[X_cols].values
        y = (Xy["era"] == "1980-1999").astype(int).values
        rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=5,
                                    random_state=0, class_weight="balanced")
        cv = StratifiedKFold(5, shuffle=True, random_state=0)
        bal = cross_val_score(rf, X, y, cv=cv, scoring="balanced_accuracy")
        auc = cross_val_score(rf, X, y, cv=cv, scoring="roc_auc")
        rf.fit(X, y)
        out["era_classifier_1956_79_vs_1980_99"] = {
            "n": int(len(Xy)),
            "class_balance": {"1956-1979": int((y == 0).sum()),
                              "1980-1999": int((y == 1).sum())},
            "balanced_accuracy_cv5": round(float(bal.mean()), 3),
            "balanced_accuracy_std": round(float(bal.std()), 3),
            "roc_auc_cv5": round(float(auc.mean()), 3),
            "feature_importances": {c: round(float(v), 3) for c, v in
                                    zip(X_cols, rf.feature_importances_)}}

    with open(OUT_DIR / "summary_stats.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))

    # ---------------- figures ----------------
    plot_real = df[(df["spud_class"] == "real") & df["has_pad"]].copy()
    order = [e for _, _, e in ERA_BINS if e in set(plot_real["era"])]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for ax, f, ttl in zip(
            axes, ["area_m2c", "compactness", "elongation", "wells_on_pad"],
            ["Pad area (m2)", "Compactness 4piA/P2",
             "Elongation (minor/major)", "Wells sharing pad"]):
        data = [plot_real.loc[plot_real["era"] == e, f].dropna()
                for e in order]
        ax.boxplot(data, tick_labels=[f"{e}\nn={len(d)}"
                                      for e, d in zip(order, data)],
                   showfliers=False)
        ax.set_title(ttl, fontsize=10)
        if f == "area_m2c":
            ax.set_yscale("log")
    fig.suptitle("Pad morphology by spud-year era (real-dated wells, "
                 f"pad within {MATCH_M:.0f} m)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_morph_by_era.png", dpi=150)

    fig2, ax = plt.subplots(figsize=(7, 4))
    classes = ["real", "sentinel_1800"]
    rates = {flag: [df[df["spud_class"] == c][flag].mean() for c in classes]
             for flag in ["has_pad", "has_pit"]}
    x = np.arange(len(classes))
    ax.bar(x - 0.18, rates["has_pad"], 0.36, label="pad within 50 m")
    ax.bar(x + 0.18, rates["has_pit"], 0.36, label="pit within 50 m")
    ax.set_xticks(x)
    ax.set_xticklabels([f"dated (n={int((df['spud_class']=='real').sum())})",
                        "sentinel 1800 "
                        f"(n={int((df['spud_class']=='sentinel_1800').sum())})"])
    ax.set_ylabel("match rate")
    ax.set_title("Annotation match rates: dated vs undated-historic wells")
    ax.legend()
    fig2.tight_layout()
    fig2.savefig(OUT_DIR / "fig_pit_pad_rates.png", dpi=150)
    print(f"wrote outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
