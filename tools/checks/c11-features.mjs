// G (leaf-1.3): motion/presence features respond to signal change.
import { run, done, fail, PYTHON, HOST_ENV, ROOT } from "./util.mjs";

const code = `
import numpy as np
from wifi_map import features
steady = [[-60.0, -70.0] for _ in range(12)]
rng = np.random.default_rng(0)
jittery = rng.normal(-60, 6, size=(24, 3)).tolist()
assert features.motion_score(steady) == 0.0
assert features.presence(steady) is False
s = features.motion_score(jittery)
assert s > 2.0, s
assert features.presence(jittery) is True
print("features ok", round(s, 3))
`;
const r = await run(PYTHON, ["-c", code], { cwd: ROOT, env: HOST_ENV, timeout: 60000 });
if (r.code !== 0 || !/features ok/.test(r.out + r.err)) fail((r.out + r.err).slice(-500));

done("features verified");
