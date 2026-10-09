// G1: hardware.md documents the board, and the live board matches it.
import { readFileSync, existsSync } from "node:fs";
import { run, done, fail, PORT, ESPTOOL } from "./util.mjs";

const doc = readFileSync("docs/hardware.md", "utf8");
for (const m of ["ESP8266EX", "2c:f4:32:2e:d4:dc", "CP2102", "4 MB"]) {
  if (!doc.includes(m)) fail(`docs/hardware.md missing "${m}"`);
}

if (!existsSync(PORT)) fail(`serial port ${PORT} not present (replug the board)`);
const r = await run(ESPTOOL, ["--port", PORT, "flash-id"], { timeout: 60000 });
if (r.code !== 0) fail(`esptool flash-id failed: ${(r.err || r.out).slice(0, 400)}`);
const out = r.out + r.err;
if (!/ESP8266/.test(out)) fail("chip is not reported as ESP8266");
if (!/2c:f4:32:2e:d4:dc/i.test(out)) fail("live MAC differs from the documented MAC");

done("hardware doc verified");
