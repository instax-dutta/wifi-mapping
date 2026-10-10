// G (leaf-1.4): the UI is served and structurally complete.
import { setTimeout as sleep } from "node:timers/promises";
import { spawnBg, done, fail, PYTHON, HOST_ENV, ROOT } from "./util.mjs";

const HTTP = 3988;
const srv = spawnBg(PYTHON,
  ["-m", "wifi_map.server", "--source", "udp", "--udp-port", "5988",
   "--session", "fixtures/golden", "--port", String(HTTP)],
  { cwd: ROOT, env: HOST_ENV });
await sleep(1600);
try {
  const html = await (await fetch(`http://127.0.0.1:${HTTP}/`)).text();
  for (const id of ["status-link", "status-motion", "status-map", "status-samples",
                    "map", "aps", "motion-score", "env-drift", "pos-x", "pos-y"]) {
    if (!html.includes(`id="${id}"`)) fail(`UI missing element #${id}`);
  }
  const css = await fetch(`http://127.0.0.1:${HTTP}/static/styles.css`);
  const js = await fetch(`http://127.0.0.1:${HTTP}/static/app.js`);
  if (!css.ok || !(css.headers.get("content-type") || "").includes("text/css")) fail("css not served");
  if (!js.ok || !(js.headers.get("content-type") || "").includes("javascript")) fail("js not served");
} finally {
  srv.child.kill("SIGTERM");
}
done("ui verified");
