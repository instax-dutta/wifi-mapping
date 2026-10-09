import json

from wifi_map.records import ScanFrame, SniffFrame, parse_line, to_wire


def test_parse_scan_frame():
    line = json.dumps({
        "t": "scan", "seq": 5, "ms": 1234, "n": 2,
        "aps": [
            {"b": "aa:bb:cc:dd:ee:01", "s": "Home", "r": -55, "c": 6, "e": 3, "h": 0},
            {"b": "aa:bb:cc:dd:ee:02", "s": "", "r": -80, "c": 11, "e": 0, "h": 1},
        ],
    })
    f = parse_line(line)
    assert isinstance(f, ScanFrame)
    assert f.seq == 5 and f.ms == 1234
    assert len(f.aps) == 2
    assert f.aps[0].bssid == "aa:bb:cc:dd:ee:01"
    assert f.aps[0].rssi == -55
    assert f.aps[1].hidden is True


def test_parse_sniff_frame():
    f = parse_line(json.dumps({"t": "pk", "seq": 1, "ms": 9, "b": "aa:bb:cc:dd:ee:01",
                               "r": -60, "c": 1, "len": 128}))
    assert isinstance(f, SniffFrame)
    assert f.rssi == -60 and f.length == 128


def test_parse_non_frame():
    assert parse_line("") is None
    assert parse_line("garbage not json") is None
    boot = parse_line(json.dumps({"t": "boot", "fw": "wifi-mapper"}))
    assert isinstance(boot, dict) and boot["t"] == "boot"


def test_bad_json_raises():
    try:
        parse_line("{not json")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_to_wire_roundtrip_scan():
    f = parse_line(json.dumps({
        "t": "scan", "seq": 2, "ms": 100, "n": 1,
        "aps": [{"b": "aa:bb:cc:dd:ee:01", "s": "x", "r": -50, "c": 6, "e": 3, "h": 0}],
        "x": 1.0, "y": 2.0,
    }))
    w = to_wire(f)
    assert w["aps"][0]["b"] == "aa:bb:cc:dd:ee:01"
    assert w["x"] == 1.0 and w["y"] == 2.0
    assert parse_line(json.dumps(w)).aps[0].rssi == -50
