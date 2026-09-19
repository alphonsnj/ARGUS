// Generates a private runtime credential artifact; never logs its contents.
import { spawnSync } from "node:child_process";
import { open } from "node:fs/promises";
import path from "node:path";
import { serializeRuntimeEnv } from "./runtime-env.mjs";

const output = path.resolve(".env.runtime");
if (process.argv.slice(2).some(arg => arg !== "--rotate")) throw new Error("Unknown option");
// Reserve before changing the database; refuse overwrite/implicit password rotation.
const file = await open(output, "wx", 0o600);
try {
  const result = spawnSync("docker", ["compose", "run", "--rm", "--no-deps", "-T",
    "-v", `${process.cwd()}/scripts:/ops:ro`, "--entrypoint", "python", "migrate",
    "/ops/provision_runtime.py", ...process.argv.slice(2)], { encoding: "utf8" });
  if (result.status !== 0) throw new Error("Provisioning failed. Inspect prerequisites; no secrets logged.");
  const values = JSON.parse(result.stdout);
  await file.writeFile(serializeRuntimeEnv(values));
  console.log("Created .env.runtime (0600). Set ARGUS_APP_ENV_FILE=.env.runtime in .env, then recreate API/worker.");
} finally {
  await file.close();
}
