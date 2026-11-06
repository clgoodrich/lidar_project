import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import expkit as ek  # noqa: E402


def test_paths():
    assert ek.exp_dir("4.4").name == "4_4_methane_plumes"
    assert ek.exp_dir("p1").name == "p1_splits_manifests"


def test_recall_at_k_ties_and_duplicates():
    r = ek.recall_at_k([0.9, 0.9, 0.5, 0.1], ["a", "a", None, "b"], [1, 1, 1, 2], {1: 1, 2: 1, 3: 0},
                       area_km2=0.075, k_per_km2=40)
    assert r["k"] == 3 and r["hits"] == 1 and r["n_truth"] == 2 and r["recall"] == 0.5


def test_bootstrap_and_decide():
    blocks = list(range(30))
    p, lo, hi, _ = ek.block_bootstrap(lambda b: float(np.mean(b)), blocks, B=200)
    assert lo < p < hi
    assert ek.decide(-0.01, 0.05, 0.03) == "success"
    assert ek.decide(-0.10, -0.05, 0.03) == "failure"
    assert ek.decide(-0.05, 0.02, 0.03) == "inconclusive"


def test_intervals():
    _, lo, hi = ek.clopper_pearson(0, 10)
    assert lo == 0 and 0.30 < hi < 0.31
    d, lo, hi = ek.newcombe_diff(56, 70, 48, 80)
    assert lo < d < hi and abs(lo - 0.0524) < 2e-3
    assert ek.n_for_proportion(0.15, deff=1.0) == 43


def test_calibration_and_run(tmp_path):
    c = ek.calibration([0, 1, 1, 0], [0.1, 0.9, 0.8, 0.2])
    assert c["brier"] < 0.05
    d = ek.new_run("4.4", "smoke", {"a": 1}, base=tmp_path)
    ek.write_provenance(d, inputs=[Path(__file__)])
    assert (d / "_PROVENANCE.json").exists() and (d / "_RUN.md").exists()
