// G (leaf-1.2): the server ingests UDP frames and serves live state.
import { readFileSync } from "node:fs";
import dgram from "node:dgram";
import { setTimeout as sleep } from "node:timers/promises";
import { spawnBg, done, fail, PYTHON, HOST_ENV, ROOT } from "./util.mjs";

const HTTP = 3987, UDP = 5987;
const srv = spawnBg(PYTHON,
  ["-m", "wifi_map.server", "--source", "udp", "--udp-port", String(UDP),
   "--session", "fixtures/golden", "--port", String(HTTP)],
  { cwd: ROOT, env: HOST_ENV });
await sleep(1600);
if (srv.child.exitCode !== null) fail("server exited early: " + srv.out() + srv.err());

const line = readFileSync("fixtures/golden/scans.jsonl", "utf8").split("\n").filter(Boolean)[0];
const sock = dgram.createSocket("udp4");
await new Promise((res) => sock.send(Buffer.from(line + "\n"), UDP, "127.0.0.1", () => res()));
await sleep(600);

let st;
try {
  const res = await fetch(`http://127.0.0.1:${HTTP}/api/state`);
  if (!res.ok) fail("state http " + res.status);
  st = await res.json();
} finally {
  srv.child.kill("SIGTERM");
  sock.close();
}

if (!st.connected) fail("server did not register a connection");
if (st.samples < 1) fail("no samples ingested");
if (!st.position) fail("no position (session not fitted)");

done("live server verified");
