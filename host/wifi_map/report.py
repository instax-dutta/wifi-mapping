"""Render a self-contained HTML report from an analysis output directory.

Usage (from the repo root):
    PYTHONPATH=host .venv/bin/python -m wifi_map.report --dir data/derived/room1
Writes report.html next to metrics.json, with figures embedded as base64 so the
file can be opened or moved on its own.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
from typing import Any, Dict


def _embed(path: Path, caption: str) -> str:
    if not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode()
    return (f'<figure><img src="data:image/png;base64,{b64}" alt="{html.escape(path.name)}">'
            f'<figcaption>{html.escape(caption)}</figcaption></figure>')


def _table(rows: Dict[str, Any]) -> str:
    body = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
                   for k, v in rows.items())
    return f"<table>{body}</table>"


def render(analysis_dir: Path) -> Path:
    m = json.loads((analysis_dir / "metrics.json").read_text())
    parts = [f"<h1>WiFi radio map report</h1>",
             f"<p class='sub'>{html.escape(m.get('session', ''))} - "
             f"{m.get('samples')} samples, {m.get('unique_aps')} APs</p>"]

    summary = {"samples": m.get("samples"), "unique_aps": m.get("unique_aps")}
    if m.get("localization"):
        loc = m["localization"]
        summary.update({"localization median (units)": round(loc["median_m"], 3),
                        "localization p90 (units)": round(loc["p90_m"], 3),
                        "kNN k": loc["k"]})
    if m.get("path_loss_n_mean") is not None:
        summary["path-loss exponent n (mean)"] = round(m["path_loss_n_mean"], 3)
    parts.append("<h2>Summary</h2>" + _table(summary))

    if m.get("path_loss_fits"):
        fits = {b: f"n={v['n']:.2f}, P0={v['p0']:.1f} dBm, {v['n_samples']} pts"
                for b, v in m["path_loss_fits"].items()}
        parts.append("<h2>Path-loss fits</h2>" + _table(fits))

    if m.get("k_walls"):
        kw = m["k_walls"]
        parts.append("<h2>k-wall thresholds (RSSI -> wall count)</h2>")
        parts.append(f"<p>AP {html.escape(kw['bssid'])}: thresholds "
                     f"{[round(t,1) for t in kw['thresholds']]}, "
                     f"k-histogram {kw['k_histogram']}</p>")

    if m.get("ap_stats"):
        rows = {s["ssid"] or s["bssid"]: f"ch{s['channel']}, median {s['median']:.0f} dBm, "
                f"jitter {s['jitter']:.0f}, n={s['n']}" for s in m["ap_stats"]}
        parts.append("<h2>Access points</h2>" + _table(rows))

    figs = []
    if (analysis_dir / "localization_loo.png").exists():
        figs.append(_embed(analysis_dir / "localization_loo.png", "localization (LOO)"))
    heat = analysis_dir / "heatmaps"
    if heat.is_dir():
        for p in sorted(heat.glob("*.png")):
            figs.append(_embed(p, f"RSSI heatmap {p.stem}"))
    if (analysis_dir / "rssi_by_ap.png").exists():
        figs.append(_embed(analysis_dir / "rssi_by_ap.png", "RSSI per AP"))
    if figs:
        parts.append("<h2>Figures</h2><div class='grid'>" + "".join(figs) + "</div>")

    doc = ("<!doctype html><meta charset='utf-8'><title>WiFi map report</title>"
           "<style>body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;"
           "max-width:960px;margin:24px auto;padding:0 16px;color:#1a1a1a}"
           "h1{margin-bottom:2px}.sub{color:#666;margin-top:0}"
           "table{border-collapse:collapse;margin:8px 0 16px}"
           "th,td{border:1px solid #ddd;padding:4px 10px;text-align:left}"
           "th{background:#f6f6f6}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}"
           "figure{margin:0}img{width:100%;border:1px solid #eee;border-radius:6px}"
           "figcaption{color:#666;font-size:12px;margin-top:4px}</style>"
           + "".join(parts))
    out = analysis_dir / "report.html"
    out.write_text(doc)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Render an HTML report from an analysis dir.")
    p.add_argument("--dir", required=True)
    args = p.parse_args(argv)
    out = render(Path(args.dir))
    print(f"REPORT OK {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
