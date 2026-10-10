// G (leaf-1.1): firmware with UDP support compiles.
import { readFileSync } from "node:fs";
import { run, done, fail, FQBN } from "./util.mjs";

const src = readFileSync("firmware/wifi_mapper/wifi_mapper.ino", "utf8");
for (const tok of ["WiFiUdp.h", '"udp ', '"join ']) {
  if (!src.includes(tok)) fail(`firmware missing token ${tok}`);
}
const r = await run("arduino-cli", ["compile", "-b", FQBN, "firmware/wifi_mapper"],
  { timeout: 300000 });
if (r.code !== 0) fail("compile failed: " + (r.out + r.err).slice(-600));

done("firmware udp compiled");
