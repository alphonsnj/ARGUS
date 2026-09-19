import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, appendFile, readFile, writeFile, mkdir, rmdir } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const suffix = `${Date.now()}`;
const source = `argus-drill-${suffix}`;
const target = `argus-restore-${suffix}`;
const root = await mkdtemp(path.join(os.tmpdir(), "argus-backup-drill-"));
const archive = path.join(root, "archive");
const config = "docker-compose.recovery.yml";
function command(executable, args, ok = true) {
  const result = spawnSync(executable, args, { encoding: "utf8" });
  if (ok && result.status !== 0) throw new Error(result.stderr || result.error?.message);
  return result;
}
const compose = (project, ...args) => command("docker", ["compose", "-p", project, "-f", config, ...args]);
const fixture = (project, action) => command("docker", ["run", "--rm", "--network", `${project}_default`,
  "--env-file", ".env", "-v", `${process.cwd()}/scripts:/ops:ro`, "--entrypoint", "python",
  "argus-api", "/ops/qa_recovery_fixture.py", action]);
const backup = (action, project, ok = true) => command("node", ["scripts/backup.mjs", action, project, archive, config], ok);
try {
  for (const project of [source, target]) compose(project, "up", "-d", "--wait");
  command("docker", ["run", "--rm", "--network", `${source}_default`, "--env-file", ".env",
    "--entrypoint", "alembic", "argus-api", "upgrade", "head"]);
  fixture(source, "seed");
  const saved = backup("backup", source);
  console.log(saved.stdout.trim());
  const lock = path.resolve("backups", ".locks", source);
  await mkdir(lock);
  try {
    assert.match(backup("backup", source, false).stderr, /lock exists/);
  } finally { await rmdir(lock); }
  assert.notEqual(backup("backup", source, false).status, 0, "must refuse backup overwrite");
  assert.notEqual(backup("restore", "argus", false).status, 0, "must refuse main project");
  const objectIndex = JSON.parse(await readFile(path.join(archive, "objects.json"), "utf8"));
  const file = path.join(archive, "objects", objectIndex[0].file);
  const original = await readFile(file);
  await appendFile(file, "corruption");
  const corrupt = backup("restore", target, false);
  assert.notEqual(corrupt.status, 0);
  assert.match(corrupt.stderr, /checksum mismatch/);
  await writeFile(file, original);
  const dumpPath = path.join(archive, "database.dump");
  const dumpBytes = await readFile(dumpPath);
  await appendFile(dumpPath, "corruption");
  assert.match(backup("restore", target, false).stderr, /checksum mismatch/);
  await writeFile(dumpPath, dumpBytes);
  const restored = backup("restore", target);
  console.log(restored.stdout.trim());
  console.log(fixture(target, "verify").stdout.trim());
  console.log(command("docker", ["run", "--rm", "--network", `${target}_default`,
    "--env-file", ".env", "-v", `${process.cwd()}/scripts:/ops:ro`, "--entrypoint", "python",
    "argus-api", "/ops/qa_database_roles.py"]).stdout.trim());
  const nonempty = backup("restore", target, false);
  assert.notEqual(nonempty.status, 0);
  assert.match(nonempty.stderr, /empty database/);
  console.log("PASS object/dump corruption, locking, overwrite, main-project and nonempty-target refusal");
  console.log(`Synthetic backup retained at ${archive}`);
} finally {
  // These exact projects were freshly created above and contain synthetic data only.
  for (const project of [source, target]) compose(project, "down", "--volumes");
}
