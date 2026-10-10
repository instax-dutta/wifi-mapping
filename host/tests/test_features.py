import numpy as np

from wifi_map import features
from wifi_map.envmap import EnvBaseline


def test_motion_low_when_steady():
    hist = [[-60, -70] for _ in range(10)]
    assert features.motion_score(hist) == 0.0
    assert features.presence(hist) is False
    assert features.motion_level(0.0) == "low"


def test_motion_high_when_jittery():
    rng = np.random.default_rng(0)
    hist = rng.normal(-60, 6, size=(20, 3)).tolist()
    score = features.motion_score(hist)
    assert score > 2.0
    assert features.presence(hist) is True
    assert features.motion_level(score) in ("medium", "high")


def test_envmap_detects_change():
    base = EnvBaseline().build([{"bssid": "aa", "median": -50.0},
                                {"bssid": "bb", "median": -70.0}])
    same = base.drift([{"bssid": "aa", "median": -51.0},
                       {"bssid": "bb", "median": -69.0}])
    assert same["changed"] is False
    moved = base.drift([{"bssid": "aa", "median": -70.0},
                        {"bssid": "bb", "median": -70.0}])
    assert moved["changed"] is True
    assert moved["per_ap"]["aa"] == 20.0
