// G3: the firmware compiles for the target board.
import { run, done, fail, FQBN } from "./util.mjs";

const r = await run("arduino-cli", ["compile", "-b", FQBN, "firmware/wifi_mapper"],
  { timeout: 300000 });
if (r.code !== 0) fail(`compile failed:\n${(r.out + r.err).slice(-800)}`);
if (!/Sketch uses|bytes/.test(r.out + r.err)) fail("compile produced no size report");

done("firmware compiled");
