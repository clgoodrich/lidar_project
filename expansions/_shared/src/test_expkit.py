import sys
from pathlib import Path

import numpy as np
import pytest

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


def test_decide_invalid_evidence_and_boundaries():
    import pytest
    for kind in ("noninferiority", "superiority"):
        for lo, hi in ((0.1, np.nan), (np.nan, 0.2), (0.2, -0.2), (0.1, np.inf)):
            assert ek.decide(lo, hi, 0.05, kind) == "inconclusive"
        for margin in (-0.1, np.nan, np.inf):
            with pytest.raises(ValueError):
                ek.decide(0.1, 0.2, margin, kind)
    assert ek.decide(-0.05, -0.05, 0.05) == "inconclusive"
    assert ek.decide(0.05, 0.05, 0.05, "superiority") == "inconclusive"


def test_calibration_and_run(tmp_path):
    c = ek.calibration([0, 1, 1, 0], [0.1, 0.9, 0.8, 0.2])
    assert c["brier"] < 0.05
    d = ek.new_run("4.4", "smoke", {"a": 1}, base=tmp_path)
    ek.write_provenance(d, inputs=[Path(__file__)])
    assert (d / "_PROVENANCE.json").exists() and (d / "_RUN.md").exists()


def test_bootstrap_counts_undefined_draws():
    # SH-01. 1 of 10 blocks holds truth: many resamples have no truth. The interval must not
    # collapse to [1, 1] by dropping them.
    blocks = [(1, 1)] + [(0, 0)] * 9
    stat = lambda bl: (sum(h for h, _ in bl) / sum(n for _, n in bl)) if sum(n for _, n in bl) else float("nan")
    p, lo, hi, d = ek.block_bootstrap(stat, blocks, B=500, seed=1)
    assert ek.undefined_share(d) > 0.2
    assert np.isnan(lo) and np.isnan(hi)
    assert ek.decide(lo, hi, 0.05) == "inconclusive"
    _, lo2, hi2, _ = ek.block_bootstrap(stat, blocks, B=500, seed=1, max_undefined=0.5)
    assert np.isfinite(lo2) and np.isfinite(hi2)


def test_recall_scope_check():
    # SH-02. Hits on truth outside the denominator are ignored when eligible_truth is given, and raise otherwise.
    r = ek.recall_at_k([0.9, 0.8, 0.7], [1, 2, 3], [0, 0, 0], {0: 1}, 1.0, eligible_truth={1})
    assert r["recall"] == 1.0 and r["hits"] == 1
    with pytest.raises(AssertionError):
        ek.recall_at_k([0.9, 0.8, 0.7], [1, 2, 3], [0, 0, 0], {0: 1}, 1.0)


def test_policy_and_readers(tmp_path):
    assert ek.policy_for("pit_floor")["cutoff"] == 0.35
    assert ek.policy_for("pad")["cutoff"] == 0.525
    assert ek.policy_for("pad", "sensitivity")["cutoff"] == 0.10
    with pytest.raises(AssertionError):
        ek.assert_same_policy(ek.policy_for("pit_floor"), ek.policy_for("pit_floor", "sensitivity"))
    b = tmp_path / "buf.json"
    b.write_text('{"buffer_m": 100.0}')
    assert ek.read_buffer("pit_floor", b) == 100.0
    with pytest.raises(KeyError):
        ek.read_buffer("pad", b)
    with pytest.raises(FileNotFoundError):
        ek.require_audit(tmp_path / "none.csv")
    assert ek.require_audit(tmp_path / "none.csv", allow_missing=True) is None
    c = tmp_path / "s.csv"
    c.write_text("block_id,fold,role\n1,0,val\n2,0,heldout\n3,0,train\n")
    assert set(ek.read_split_csv(c).role) == {"inner_val", "held_out", "train"}
