from pathlib import Path

import numpy as np

from wifi_map.analyze import analyze
from wifi_map.geometry import assign_k, k_thresholds
from wifi_map.sessions import ap_table, labels, load_session
from wifi_map.simulate import generate


def test_synthetic_pipeline(tmp_path: Path):
    sim = tmp_path / "sim"
    generate(sim, points=6, n_aps=4, seed=7)
    data = load_session(sim)
    bssids, X, M = ap_table(data["scans"])
    xs, ys, labeled = labels(data["scans"])
    assert labeled
    assert X.shape[0] == 36
    assert X.shape[1] == 4
    assert M.all()  # every AP seen at every point in this synthetic model

    out = tmp_path / "report"
    result = analyze(str(sim), out_dir=out, k=3)
    assert result["samples"] == 36
    assert "localization" in result
    # nearest-neighbour on a smooth path-loss field must beat random guessing
    assert result["localization"]["median_m"] < 2.5

    assert (out / "metrics.json").exists()
    assert (out / "localization_loo.png").exists()


def test_k_thresholds_and_assign():
    rssis = np.array([-40, -42, -58, -60, -75, -77, -90], dtype=float)
    thr = k_thresholds(rssis, k_max=3)
    assert len(thr) == 3
    # thresholds are ordered strongest -> weakest
    assert thr[0] > thr[1] > thr[2]
    assert assign_k(-39, thr) == 0
    assert assign_k(-60, thr) >= 1
    assert assign_k(-95, thr) == 3


def test_multi_file_session_merge(tmp_path: Path):
    # a survey directory holds one file per point; load_session merges them
    import json

    d = tmp_path / "survey"
    d.mkdir()
    for i, (x, y, rssi) in enumerate([(0.0, 0.0, -50), (1.0, 0.0, -60), (2.0, 0.0, -70)]):
        line = json.dumps({
            "t": "scan", "seq": i, "ms": i * 1000, "n": 1,
            "aps": [{"b": "aa:bb:cc:00:00:00", "s": "ref", "r": rssi, "c": 6, "e": 0, "h": 0}],
            "x": x, "y": y,
        })
        (d / f"p_{i}.jsonl").write_text(line + "\n")

    data = load_session(d)
    assert len(data["scans"]) == 3
    _, X, M = ap_table(data["scans"])
    assert X.shape == (3, 1)
    assert list(X[:, 0]) == [-50, -60, -70]

