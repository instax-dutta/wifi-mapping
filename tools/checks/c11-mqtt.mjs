// G (leaf-1.3): the MQTT publisher is import-safe and degrades gracefully.
import { run, done, fail, PYTHON, HOST_ENV, ROOT } from "./util.mjs";

const code = `
from wifi_map.mqtt import Publisher
p = Publisher()                      # no host -> must be inert, not raise
assert p.available is False
assert p.publish({'x': 1}) is False
p2 = Publisher(host=None, topic='wifimap/state')
p2.close()
print("mqtt ok")
`;
const r = await run(PYTHON, ["-c", code], { cwd: ROOT, env: HOST_ENV, timeout: 60000 });
if (r.code !== 0 || !/mqtt ok/.test(r.out + r.err)) fail((r.out + r.err).slice(-500));

done("mqtt verified");
