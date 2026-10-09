// G4: firmware flashes and a real scan of ambient APs comes back over serial.
import { existsSync, readFileSync, mkdirSync } from "node:fs";
import { run, done, fail, sleep, PORT, FQBN, PYTHON, ESPTOOL } from "./util.mjs";

const BIN = "build/wifi_mapper.ino.bin";
if (!existsSync(BIN)) {
  const c = await run("arduino-cli",
    ["compile", "-b", FQBN, "--output-dir", "build", "firmware/wifi_mapper"],
    { timeout: 300000 });
  if (c.code !== 0) fail("compile failed: " + (c.out + c.err).slice(-500));
}

const f = await run(ESPTOOL,
  ["--port", PORT, "--baud", "115200", "write-flash", "0x0", BIN],
  { timeout: 180000 });
if (f.code !== 0) fail("flash failed: " + (f.out + f.err).slice(-600));
await sleep(1500);

mkdirSync("data/derived/gate_c4", { recursive: true });
const cap = await run(PYTHON,
  ["-m", "wifi_map.capture", "--port", PORT,
   "--out", "../data/derived/gate_c4/scans.jsonl", "--duration", "10"],
  { cwd: "host", timeout: 60000 });
if (cap.code !== 0) fail("capture failed: " + (cap.out + cap.err).slice(-500));

const lines = readFileSync("data/derived/gate_c4/scans.jsonl", "utf8")
  .split("\n").filter(Boolean);
let frames = 0, aps = 0, plausible = 0;
for (const l of lines) {
  let d;
  try { d = JSON.parse(l); } catch { continue; }
  if (d.t !== "scan") continue;
  frames++;
  for (const a of d.aps || []) {
    aps++;
    if (Number.isInteger(a.r) && a.r <= 0 && a.r >= -100) plausible++;
  }
}
if (frames < 3) fail(`only ${frames} scan frames`);
if (aps < 1) fail("no access points seen (WiFi antenna/environment?)");
if (plausible < 1) fail("no plausible RSSI values");

done(`hardware scan verified frames=${frames} aps=${aps}`);
