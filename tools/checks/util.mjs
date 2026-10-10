import { spawn } from "node:child_process";
import path from "node:path";

export const ROOT = process.cwd();
export const PORT = "/dev/cu.usbserial-0001";
export const FQBN = "esp8266:esp8266:nodemcuv2";
export const PYTHON = path.join(ROOT, ".venv", "bin", "python");
export const ESPTOOL = path.join(ROOT, ".venv", "bin", "esptool");
export const HOST_ENV = { ...process.env, PYTHONPATH: path.join(ROOT, "host") };

export function run(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, {
      cwd: opts.cwd,
      env: opts.env || process.env,
      timeout: opts.timeout ?? 120000,
    });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));
    child.on("error", (e) => resolve({ code: -1, out, err: err + String(e) }));
    child.on("close", (code) => resolve({ code, out, err }));
  });
}

export function spawnBg(cmd, args, opts = {}) {
  const child = spawn(cmd, args, { cwd: opts.cwd, env: opts.env || process.env });
  let out = "";
  let err = "";
  child.stdout.on("data", (d) => (out += d));
  child.stderr.on("data", (d) => (err += d));
  return { child, out: () => out, err: () => err };
}

export function done(marker) {
  console.log(marker);
  process.exit(0);
}

export function fail(message) {
  console.error("CHECK FAILED: " + message);
  process.exit(1);
}

export function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
