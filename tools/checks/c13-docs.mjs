// G (leaf-1.5): ADRs and the capability matrix exist and are indexed.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { done, fail } from "./util.mjs";

if (!existsSync("docs/capability-matrix.md")) fail("missing docs/capability-matrix.md");
if (!existsSync("docs/adr/README.md")) fail("missing docs/adr/README.md");

const idx = readFileSync("docs/adr/README.md", "utf8");
const adrs = readdirSync("docs/adr").filter((f) => /^000\d-.*\.md$/.test(f));
if (adrs.length < 8) fail(`expected >=8 ADRs, found ${adrs.length}`);
for (const a of adrs) if (!idx.includes(a)) fail(`ADR index does not list ${a}`);

const matrix = readFileSync("docs/capability-matrix.md", "utf8").toLowerCase();
for (const tok of ["rssi", "csi", "pose", "breathing"]) {
  if (!matrix.includes(tok)) fail(`capability matrix missing "${tok}"`);
}

done("docs verified");
