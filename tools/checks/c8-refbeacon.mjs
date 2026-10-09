// G9: the reference beacon (Board B) is visible to and sniffable by the sensor (Board A).
import { readFileSync, mkdirSync } from "node:fs";
import { run, done, fail, PORT, PYTHON } from "./util.mjs";

const SSID = "mq-ref";
mkdirSync("data/derived/gate_c8", { recursive: true });

// scan for the reference AP
let r = await run(PYTHON,
  ["-m", "wifi_map.capture", "--port", PORT,
   "--out", "../data/derived/gate_c8/scan.jsonl", "--duration", "8"],
  { cwd: "host", timeout: 60000 });
if (r.code !== 0) fail("scan capture failed: " + (r.out + r.err).slice(-400));

const lines = readFileSync("data/derived/gate_c8/scan.jsonl", "utf8").split("\n").filter(Boolean);
let ref = null;
for (const l of lines) {
  let d;
  try { d = JSON.parse(l); } catch { continue; }
  if (d.t !== "scan") continue;
  for (const a of d.aps || []) {
    if (a.s === SSID) ref = a;
  }
}
if (!ref) fail(`reference AP "${SSID}" not seen - is Board B powered and running ref_beacon?`);

// sniff the reference AP's beacons
r = await run(PYTHON,
  ["-m", "wifi_map.capture", "--port", PORT,
   "--out", "../data/derived/gate_c8/sniff.jsonl", "--duration", "8",
   "--sniff", ref.b, "--sniff-channel", String(ref.c)],
  { cwd: "host", timeout: 60000 });
if (r.code !== 0) fail("sniff capture failed: " + (r.out + r.err).slice(-400));

const sl = readFileSync("data/derived/gate_c8/sniff.jsonl", "utf8").split("\n").filter(Boolean);
let pk = 0, sum = 0, n = 0;
for (const l of sl) {
  let d;
  try { d = JSON.parse(l); } catch { continue; }
  if (d.t !== "pk") continue;
  pk++; sum += d.r; n++;
}
if (pk < 5) fail(`only ${pk} beacon packets sniffed from ${SSID}`);
const mean = sum / n;

done(`reference beacon verified ssid=${SSID} ch=${ref.c} rssi=${ref.r} pk=${pk} mean=${mean.toFixed(1)}`);
