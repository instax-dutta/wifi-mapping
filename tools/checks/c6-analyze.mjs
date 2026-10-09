// G6: the analysis pipeline builds a map and localizes on synthetic data.
import { existsSync, readFileSync, rmSync } from "node:fs";
import { run, done, fail, PYTHON } from "./util.mjs";

rmSync("data/derived/gate_c6", { recursive: true, force: true });

let r = await run(PYTHON,
  ["-m", "wifi_map.simulate", "--out", "../data/derived/gate_c6/sim", "--points", "8"],
  { cwd: "host", timeout: 60000 });
if (r.code !== 0) fail("simulate failed: " + (r.out + r.err).slice(-400));

r = await run(PYTHON,
  ["-m", "wifi_map.analyze", "--session", "../data/derived/gate_c6/sim",
   "--out", "../data/derived/gate_c6/report"],
  { cwd: "host", timeout: 60000 });
if (r.code !== 0) fail("analyze failed: " + (r.out + r.err).slice(-400));
if (!/ANALYSIS OK/.test(r.out)) fail("analyze did not print ANALYSIS OK");

const m = JSON.parse(readFileSync("data/derived/gate_c6/report/metrics.json", "utf8"));
const med = m?.localization?.median_m;
if (typeof med !== "number" || !(med < 1.5)) fail(`synthetic median error ${med} not < 1.5 m`);
if (!existsSync("data/derived/gate_c6/report/localization_loo.png")) fail("no localization figure");

done(`analysis pipeline verified median_error_m=${med.toFixed(3)}`);
