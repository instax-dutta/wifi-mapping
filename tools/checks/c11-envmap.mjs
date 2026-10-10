// G (leaf-1.3): environment drift detects a changed map.
import { run, done, fail, PYTHON, HOST_ENV, ROOT } from "./util.mjs";

const code = `
from wifi_map.envmap import EnvBaseline
b = EnvBaseline().build([{'bssid':'aa','median':-50.0},{'bssid':'bb','median':-70.0}])
same = b.drift([{'bssid':'aa','median':-51.0},{'bssid':'bb','median':-69.0}])
assert same['changed'] is False, same
moved = b.drift([{'bssid':'aa','median':-72.0},{'bssid':'bb','median':-70.0}])
assert moved['changed'] is True, moved
assert moved['per_ap']['aa'] == 22.0
print("envmap ok")
`;
const r = await run(PYTHON, ["-c", code], { cwd: ROOT, env: HOST_ENV, timeout: 60000 });
if (r.code !== 0 || !/envmap ok/.test(r.out + r.err)) fail((r.out + r.err).slice(-500));

done("envmap verified");
