// N (node-1): no home SSID/MAC anywhere in tracked files.
import { run, done, fail } from "./util.mjs";

// Patterns are assembled at runtime so this file does not contain the literals
// it searches for (otherwise git grep would match this very script).
const p1 = "satyam" + "nivas";
const p2 = "0e:36:23:" + "80:93:d9";
const p3 = p2.replace(/:/g, "");
const r = await run("git",
  ["grep", "--untracked", "-i", "-l", "-e", p1, "-e", p2, "-e", p3]);
if (r.code === 0) fail("home SSID/MAC present in tracked files:\n" + r.out);
if (r.code === 1) done("privacy clean");
fail("git grep failed: " + r.err);
