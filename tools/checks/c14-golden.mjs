// G (leaf-1.6): the golden fixture reproduces its expected outputs.
import { run, done, fail, PYTHON } from "./util.mjs";

const r = await run(PYTHON, ["-m", "pytest", "-q", "tests/test_golden.py"],
  { cwd: "host", timeout: 120000 });
const o = r.out + r.err;
if (r.code !== 0 || !/passed/.test(o)) fail("golden test failed:\n" + o.slice(-600));

done("golden verified");
