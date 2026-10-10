import json
from pathlib import Path

import numpy as np

from wifi_map.analyze import error_stats, knn_loo
from wifi_map.index import FingerprintIndex
from wifi_map.sessions import ap_table, labels, load_session

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "fixtures" / "golden"
EXPECTED = json.loads((ROOT / "fixtures" / "golden_expected.json").read_text())


def _fixture():
    d = load_session(FIX)
    b, X, M = ap_table(d["scans"])
    xs, ys, _ = labels(d["scans"])
    pos = np.stack([xs, ys], axis=1)
    good = np.isfinite(pos).all(axis=1)
    return b, X[good], pos[good]


def test_index_localizes_known_point():
    b, X, pos = _fixture()
    idx = FingerprintIndex().fit(b, X, pos)
    xy, err = idx.query(X[0])
    assert np.allclose(xy, EXPECTED["query0_xy"], atol=1e-4)
    assert abs(err - EXPECTED["query0_err"]) < 1e-4


def test_golden_median_matches_reference():
    b, X, pos = _fixture()
    pred = knn_loo(X, pos, k=3)
    st = error_stats(pred, pos)
    assert abs(st["median_m"] - EXPECTED["localization_median"]) < 1e-4
    assert X.shape[0] == EXPECTED["samples"]
    assert X.shape[1] == EXPECTED["aps"]
