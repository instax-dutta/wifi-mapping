// G7: promiscuous sniffing yields a dense per-packet RSSI stream from one AP.
import { readFileSync, mkdirSync } from "node:fs";
import { run, done, fail, PORT, PYTHON } from "./util.mjs";

function median(a) {
  const s = [...a].sort((x, y) => x - y);
  const n = s.length;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

mkdirSync("data/derived/gate_c7", { recursive: true });

let r = await run(PYTHON,
  ["-m", "wifi_map.capture", "--port", PORT,
   "--out", "../data/derived/gate_c7/scan.jsonl", "--duration", "8"],
  { cwd: "host", timeout: 60000 });
if (r.code !== 0) fail("scan capture failed: " + (r.out + r.err).slice(-400));

const lines = readFileSync("data/derived/gate_c7/scan.jsonl", "utf8").split("\n").filter(Boolean);
const agg = {};
for (const l of lines) {
  let d;
  try { d = JSON.parse(l); } catch { continue; }
  if (d.t !== "scan") continue;
  for (const a of d.aps || []) {
    (agg[a.b] ??= { ch: a.c, rs: [] }).rs.push(a.r);
  }
}
const cands = Object.entries(agg)
  .map(([b, v]) => ({ b, ch: v.ch, n: v.rs.length, med: median(v.rs) }))
  .filter((x) => x.ch >= 1 && x.ch <= 14);
cands.sort((x, y) => y.n - x.n || y.med - x.med);
if (!cands.length) fail("no AP with a usable channel found to sniff");
const t = cands[0];

r = await run(PYTHON,
  ["-m", "wifi_map.capture", "--port", PORT,
   "--out", "../data/derived/gate_c7/sniff.jsonl", "--duration", "8",
   "--sniff", t.b, "--sniff-channel", String(t.ch)],
  { cwd: "host", timeout: 60000 });
if (r.code !== 0) fail("sniff capture failed: " + (r.out + r.err).slice(-400));

const sl = readFileSync("data/derived/gate_c7/sniff.jsonl", "utf8").split("\n").filter(Boolean);
let pk = 0, plausible = 0;
for (const l of sl) {
  let d;
  try { d = JSON.parse(l); } catch { continue; }
  if (d.t !== "pk") continue;
  pk++;
  if (Number.isInteger(d.r) && d.r <= 0 && d.r >= -100) plausible++;
}
if (pk < 5) fail(`only ${pk} packets sniffed from ${t.b} (ch ${t.ch})`);
if (plausible < 5) fail("sniffed RSSI values implausible");

done(`sniffer verified pk=${pk} target=${t.b} ch=${t.ch}`);
