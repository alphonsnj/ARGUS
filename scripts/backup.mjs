import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, open, readFile, writeFile, lstat, rmdir } from "node:fs/promises";
import path from "node:path";

// Run from the repository root. No shell interpolation of credentials or paths.
const [action, project, directory, composeFile = "docker-compose.yml"] = process.argv.slice(2);
if (!["backup", "restore"].includes(action) || !/^[a-z][a-z0-9-]{2,60}$/.test(project || "") || !directory) {
  throw new Error("Usage: node scripts/backup.mjs backup|restore PROJECT DIRECTORY [COMPOSE_FILE]");
}
if (action === "restore" && !project.startsWith("argus-restore-")) {
  throw new Error("Restore only targets isolated projects named argus-restore-...");
}
process.umask(0o077);
const root = path.resolve(directory);
const compose = ["compose", "-p", project, "-f", path.resolve(composeFile)];
function docker(args, options = {}) {
  const result = spawnSync("docker", args, { encoding: "utf8", ...options });
  if (result.error || result.status !== 0) throw new Error(result.stderr || result.error?.message || "Docker failed");
  return result.stdout?.trim() || "";
}
const run = (...args) => docker([...compose, ...args]);
async function sha(file) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  return hash.digest("hex");
}
function objects(operation, writable = false) {
  docker(["run", "--rm", "--user", `${process.getuid()}:${process.getgid()}`, "--network", `${project}_default`,
    "--env-file", path.resolve(".env"),
    "--mount", `type=bind,source=${path.resolve("scripts")},target=/ops,readonly`,
    "--mount", `type=bind,source=${root},target=/backup${writable ? "" : ",readonly"}`,
    "--entrypoint", "python", "argus-api", "/ops/backup_objects.py", operation]);
}
const lockParent = path.resolve("backups", ".locks");
await mkdir(lockParent, { recursive: true, mode: 0o700 });
const lock = path.join(lockParent, project);
try { await mkdir(lock, { mode: 0o700 }); }
catch { throw new Error(`Project backup/restore lock exists: ${lock}. Check for a running operation before removing a stale lock.`); }
try {
const running = run("ps", "--status", "running", "--services").split("\n");
if (!running.includes("postgres") || !running.includes("minio")) {
  throw new Error("Target PostgreSQL and MinIO must be running");
}
const writers = running.filter(name => ["api", "document-worker"].includes(name));
const sql = query => run("exec", "-T", "postgres", "sh", "-c",
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"', "sh", query);
const started = Date.now();
if (action === "backup") {
  await mkdir(root, { mode: 0o700 }); // Refuse to reuse/overwrite an existing backup.
  try {
    if (writers.length) run("stop", "--timeout", "120", ...writers);
    const dump = await open(path.join(root, "database.dump"), "wx", 0o600);
    try {
      docker([...compose, "exec", "-T", "postgres", "sh", "-c",
        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl'],
      { stdio: ["ignore", dump.fd, "pipe"] });
    } finally { await dump.close(); }
    objects("backup", true);
    const manifest = { version: 1, project, created_at: new Date().toISOString(),
      database_sha256: await sha(path.join(root, "database.dump")),
      objects_sha256: await sha(path.join(root, "objects.json")) };
    // This file is written last; its absence means an incomplete backup.
    await writeFile(path.join(root, "manifest.json"), JSON.stringify(manifest, null, 2), { flag: "wx", mode: 0o600 });
  } finally {
    if (writers.length) run("start", ...writers);
  }
} else {
  if (writers.length) throw new Error("Stop restore-target API/worker before restoring");
  if ((await lstat(root)).isSymbolicLink()) throw new Error("Backup symlinks are not allowed");
  for (const file of ["manifest.json", "database.dump", "objects.json", "objects"]) {
    if ((await lstat(path.join(root, file))).isSymbolicLink()) throw new Error("Backup symlinks are not allowed");
  }
  const manifest = JSON.parse(await readFile(path.join(root, "manifest.json"), "utf8"));
  if (manifest.version !== 1 || manifest.project === project) throw new Error("Invalid manifest or source equals target");
  if (await sha(path.join(root, "database.dump")) !== manifest.database_sha256 ||
      await sha(path.join(root, "objects.json")) !== manifest.objects_sha256) throw new Error("Backup checksum mismatch");
  objects("verify");
  if (sql("SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema')") !== "0") {
    throw new Error("Restore requires an empty database");
  }
  objects("empty");
  const dump = await open(path.join(root, "database.dump"), "r");
  try {
    docker([...compose, "exec", "-T", "postgres", "sh", "-c",
      'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --single-transaction --exit-on-error --no-owner --no-acl'],
    { stdio: [dump.fd, "pipe", "pipe"] });
  } finally { await dump.close(); }
  objects("restore");
}
console.log(JSON.stringify({ action, project, directory: root, seconds: (Date.now() - started) / 1000 }));
} finally {
  await rmdir(lock);
}
