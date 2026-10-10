// N (node-1): UDP -> server -> SSE -> position/motion works end to end.
import { readFileSync } from "node:fs";
import dgram from "node:dgram";
import { setTimeout as sleep } from "node:timers/promises";
import { spawnBg, done, fail, PYTHON, HOST_ENV, ROOT } from "./util.mjs";

const HTTP = 3989, UDP = 5989;
const srv = spawnBg(PYTHON,
  ["-m", "wifi_map.server", "--source", "udp", "--udp-port", String(UDP),
   "--session", "fixtures/golden", "--port", String(HTTP)],
  { cwd: ROOT, env: HOST_ENV });
await sleep(1600);
if (srv.child.exitCode !== null) fail("server exited early: " + srv.out() + srv.err());

// consume the SSE stream in the background
let sseData = 0;
const ac = new AbortController();
(async () => {
  try {
    const res = await fetch(`http://127.0.0.1:${HTTP}/events`, { signal: ac.signal });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      sseData += (dec.decode(value).match(/data:/g) || []).length;
    }
  } catch { /* aborted */ }
})();

const frames = readFileSync("fixtures/golden/scans.jsonl", "utf8").split("\n").filter(Boolean);
const sock = dgram.createSocket("udp4");
for (const f of frames.slice(0, 10)) {
  await new Promise((res) => sock.send(Buffer.from(f + "\n"), UDP, "127.0.0.1", () => res()));
  await sleep(60);
}
await sleep(900);

let st;
try {
  st = await (await fetch(`http://127.0.0.1:${HTTP}/api/state`)).json();
} finally {
  ac.abort();
  srv.child.kill("SIGTERM");
  sock.close();
}

if (!st.connected) fail("not connected");
if (st.samples < 10) fail(`expected >=10 samples, got ${st.samples}`);
if (!st.position) fail("no position in state");
if (!st.motion) fail("no motion in state");
if (!("env" in st)) fail("no env in state");
if (sseData < 1) fail("SSE stream delivered no data");

done("integration verified");
