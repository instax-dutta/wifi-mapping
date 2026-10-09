// G2: the DOX tree is complete and indexed.
import { readFileSync, existsSync } from "node:fs";
import { done, fail } from "./util.mjs";

const root = readFileSync("AGENTS.md", "utf8");
if (root.includes("not yet indexed")) fail("root AGENTS.md still has the placeholder index");
if (!root.includes("## Child DOX Index")) fail("root AGENTS.md lacks a Child DOX Index");

const children = ["docs/AGENTS.md", "firmware/AGENTS.md", "host/AGENTS.md", "tools/AGENTS.md"];
for (const c of children) {
  if (!existsSync(c)) fail(`missing child doc ${c}`);
  if (!root.includes(c)) fail(`root index does not list ${c}`);
  const body = readFileSync(c, "utf8");
  for (const section of ["## Purpose", "## Ownership", "## Child DOX Index"]) {
    if (!body.includes(section)) fail(`${c} missing "${section}"`);
  }
}

done("dox tree verified");
