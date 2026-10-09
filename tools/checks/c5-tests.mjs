// G5: the host package's unit and pipeline tests pass.
import { run, done, fail, PYTHON } from "./util.mjs";

const r = await run(PYTHON, ["-m", "pytest", "-q", "tests"],
  { cwd: "host", timeout: 180000 });
const o = r.out + r.err;
if (r.code !== 0) fail("pytest failed:\n" + o.slice(-800));
if (!/passed/.test(o)) fail('no "passed" marker in pytest output');

done("tests passed");
