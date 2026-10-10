// G (leaf-1.3): the fingerprint index localizes the golden fixture.
import { run, done, fail, PYTHON, HOST_ENV, ROOT } from "./util.mjs";

const code = `
import numpy as np
from wifi_map.sessions import load_session, ap_table, labels
from wifi_map.index import FingerprintIndex
d = load_session('fixtures/golden')
b, X, M = ap_table(d['scans'])
xs, ys, _ = labels(d['scans'])
pos = np.stack([xs, ys], 1); good = np.isfinite(pos).all(1)
idx = FingerprintIndex().fit(b, X[good], pos[good])
xy, err = idx.query(X[good][0])
assert np.allclose(xy, [0.5, 0.5], atol=1e-3), xy
assert err < 1e-6, err
print("index ok")
`;
const r = await run(PYTHON, ["-c", code], { cwd: ROOT, env: HOST_ENV, timeout: 60000 });
if (r.code !== 0 || !/index ok/.test(r.out + r.err)) fail((r.out + r.err).slice(-500));

done("fingerprint index verified");
