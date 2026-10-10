/* Live dashboard client. Consumes /events (SSE) and draws the instrument. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const SVGNS = "http://www.w3.org/2000/svg";
  const map = $("map");

  const TRAIL_MAX = 60;
  let trail = [];
  let lastExtent = null;

  function chip(id, cls, text) {
    const el = $(id);
    if (!el) return;
    el.classList.remove("is-ok", "is-warn", "is-bad");
    if (cls) el.classList.add(cls);
    const b = el.querySelector("b");
    if (b && text != null) b.textContent = text;
  }

  function el(tag, attrs) {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function clamp01(v) { return Math.max(0, Math.min(1, v)); }

  function domain(extent) {
    let xmin = -1, xmax = 4, ymin = -1, ymax = 3;
    if (extent && extent.x && extent.y) {
      xmin = Math.min(extent.x[0], 0) - 0.7;
      xmax = Math.max(extent.x[1], 0) + 0.7;
      ymin = Math.min(extent.y[0], 0) - 0.7;
      ymax = Math.max(extent.y[1], 0) + 0.7;
    }
    return { xmin, xmax, ymin, ymax };
  }

  function project(x, y, d) {
    const W = 1000, H = 720, pad = 46;
    const sx = pad + ((x - d.xmin) / (d.xmax - d.xmin)) * (W - 2 * pad);
    const sy = pad + ((y - d.ymin) / (d.ymax - d.ymin)) * (H - 2 * pad);
    return [sx, sy];
  }

  function drawMap(state) {
    const d = domain(state.extent);
    map.innerHTML = "";

    // grid lines at integer tile coordinates
    for (let gx = Math.ceil(d.xmin); gx <= Math.floor(d.xmax); gx++) {
      const [sx] = project(gx, 0, d);
      map.appendChild(el("line", { x1: sx, y1: 30, x2: sx, y2: 690,
        class: gx === 0 ? "grid-line major" : "grid-line" }));
      map.appendChild(el("text", { x: sx + 4, y: 704, class: "axis-text" })).textContent = gx;
    }
    for (let gy = Math.ceil(d.ymin); gy <= Math.floor(d.ymax); gy++) {
      const [, sy] = project(0, gy, d);
      map.appendChild(el("line", { x1: 30, y1: sy, x2: 970, y2: sy,
        class: gy === 0 ? "grid-line major" : "grid-line" }));
      map.appendChild(el("text", { x: 8, y: sy - 4, class: "axis-text" })).textContent = gy;
    }

    // reference beacon at origin
    const [bx, by] = project(0, 0, d);
    map.appendChild(el("circle", { cx: bx, cy: by, r: 11, class: "beacon-ring" }));
    map.appendChild(el("circle", { cx: bx, cy: by, r: 3.5, class: "beacon-core" }));
    map.appendChild(el("text", { x: bx + 16, y: by - 12, class: "beacon-label" })).textContent = "REF";

    // trail
    if (trail.length > 1) {
      const pts = trail.map((p) => project(p[0], p[1], d).join(",")).join(" ");
      map.appendChild(el("polyline", { points: pts, class: "trail" }));
    }

    // position
    if (state.position) {
      const [px, py] = project(state.position.x, state.position.y, d);
      map.appendChild(el("circle", { cx: px, cy: py, r: 16, class: "pos-halo" }));
      map.appendChild(el("circle", { cx: px, cy: py, r: 7, class: "pos-core" }));
      map.appendChild(el("circle", { cx: px, cy: py, r: 12, class: "pos-ring" }));
      const t = el("text", { x: px + 16, y: py + 22, class: "pos-label" });
      t.textContent = state.position.x.toFixed(2) + ", " + state.position.y.toFixed(2);
      map.appendChild(t);
    }
  }

  function renderAPs(aps) {
    const ul = $("aps");
    const sorted = (aps || []).slice().sort((a, b) => b.rssi - a.rssi);
    ul.innerHTML = "";
    if (!sorted.length) {
      const li = document.createElement("li");
      li.className = "ap";
      li.innerHTML = '<span class="name">no APs yet</span>';
      ul.appendChild(li);
      return;
    }
    for (const a of sorted) {
      const li = document.createElement("li");
      const cls = a.rssi >= -60 ? "strong" : a.rssi >= -80 ? "weak" : "dead";
      li.className = "ap " + cls;
      const name = (a.ssid && a.ssid.length) ? a.ssid : a.bssid.slice(-5);
      const w = clamp01((a.rssi + 95) / 65) * 100;
      li.innerHTML =
        '<span class="name">' + name + '</span>' +
        '<span class="val">' + a.rssi + ' <span class="ch">ch' + a.channel + '</span></span>' +
        '<span class="bar"><i style="width:' + w.toFixed(1) + '%"></i></span>';
      ul.appendChild(li);
    }
  }

  function render(state) {
    // trail
    if (state.position) {
      const p = state.position;
      const last = trail[trail.length - 1];
      if (!last || Math.hypot(last[0] - p.x, last[1] - p.y) > 1e-4) {
        trail.push([p.x, p.y]);
        if (trail.length > TRAIL_MAX) trail.shift();
      }
    }
    const extentChanged = JSON.stringify(state.extent) !== JSON.stringify(lastExtent);
    if (extentChanged) { lastExtent = state.extent; }
    drawMap(state);

    renderAPs(state.aps);

    // chips
    chip("status-link", state.connected ? "is-ok" : "is-bad",
         state.connected ? "live" : "waiting");
    const mv = state.motion || { score: 0, level: "low" };
    const mvCls = mv.level === "high" ? "is-bad" : mv.level === "medium" ? "is-warn" : "is-ok";
    chip("status-motion", mvCls, mv.level);
    const envChanged = state.env && state.env.changed;
    chip("status-map", envChanged ? "is-bad" : "is-ok", envChanged ? "stale" : "fresh");
    chip("status-samples", null, String(state.samples || 0));

    // readout
    $("pos-x").textContent = state.position ? state.position.x.toFixed(2) : "--";
    $("pos-y").textContent = state.position ? state.position.y.toFixed(2) : "--";
    $("pos-err").textContent = (state.pos_err != null && isFinite(state.pos_err))
      ? state.pos_err.toFixed(2) : "--";

    // meters
    const mscore = (state.motion && state.motion.score) || 0;
    $("motion-score").textContent = mscore.toFixed(1);
    $("motion-bar").style.transform = "scaleX(" + clamp01(mscore / 12).toFixed(3) + ")";
    $("motion-level").textContent = mv.level;
    const drift = (state.env && state.env.score) || 0;
    $("env-drift").textContent = drift.toFixed(1);
    $("env-bar").style.transform = "scaleX(" + clamp01(drift / 12).toFixed(3) + ")";
    $("env-bar").classList.toggle("changed", !!envChanged);
    $("env-state").textContent = envChanged ? "changed" : "fresh";

    // meta
    $("meta-source").textContent = state.source || "--";
    $("meta-tick").textContent = state.ts ? new Date(state.ts * 1000).toLocaleTimeString() : "--";
    $("meta-aps").textContent = (state.aps || []).length;

    // overlay
    $("overlay").classList.toggle("hidden", !!state.connected);

    // footer
    $("foot-conn").textContent = (state.connected ? "link ok" : "no link") +
      " \u00b7 " + (state.source || "udp");
  }

  function connect() {
    const es = new EventSource("/events");
    es.onmessage = (e) => {
      try { render(JSON.parse(e.data)); } catch (err) { /* ignore malformed */ }
    };
    es.onerror = () => {
      chip("status-link", "is-bad", "offline");
      $("overlay").classList.remove("hidden");
    };
  }

  connect();
})();
