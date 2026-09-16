// Destructive-to-availability checks are restricted to the disposable validation project.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";

const compose = ["compose", "-p", "argus-validation", "-f", "docker-compose.yml", "-f", "docker-compose.validation.yml"];
const docker = (...args) => execFileSync("docker", args, { stdio: ["ignore", "pipe", "pipe"] }).toString();
const fixture = (...args) => docker("run", "--rm", "--network", "argus-validation_default", "--env-file", ".env", "-v", `${process.cwd()}/scripts:/qa:ro`, "--entrypoint", "python", "argus-validation-api", "/qa/qa_fixture.py", ...args);
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const account = JSON.parse(fixture("seed"));
const api = "http://localhost:8300/api/v1";
let token;
async function request(path, options = {}) {
  return fetch(api + path, { ...options, signal: AbortSignal.timeout(15000), headers: { ...options.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) } });
}
async function upload(name) {
  const form = new FormData();
  form.append("file", new Blob([Buffer.from(account.file, "base64")], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }), name);
  const response = await request("/documents", { method: "POST", body: form });
  assert.equal(response.status, 202);
  return (await response.json()).id;
}
async function waitFor(id, status, timeout = 90000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      const response = await request(`/documents/${id}`);
      if (response.ok) {
        const record = await response.json();
        if (record.status === status) {
          assert.equal(record.sha256, createHash("sha256").update(Buffer.from(account.file, "base64")).digest("hex"));
          return record;
        }
        assert.ok(!["failed", "rejected"].includes(record.status), `Unexpected status: ${record.status}`);
      }
    } catch (error) { if (error.code === "ERR_ASSERTION") throw error; }
    await sleep(500);
  }
  throw new Error(`Timed out waiting for ${status}`);
}
try {
  const login = await request("/auth/token", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: account.email, password: account.password }) });
  assert.equal(login.status, 200);
  token = (await login.json()).access_token;

  docker(...compose, "stop", "redis");
  const redisId = await upload("redis-outage.docx");
  await waitFor(redisId, "ready");
  docker(...compose, "start", "redis");
  console.log("PASS Redis stopped: upload accepted and database reconciliation completed it");

  docker(...compose, "pause", "clamav");
  const killedId = await upload("worker-crash.docx");
  await waitFor(killedId, "processing");
  docker(...compose, "kill", "-s", "SIGKILL", "document-worker");
  docker(...compose, "unpause", "clamav");
  docker("start", "argus-validation-document-worker-1");
  await waitFor(killedId, "ready");
  console.log("PASS Worker SIGKILL during processing: accepted upload recovered");

  docker(...compose, "stop", "document-worker");
  const postgresId = await upload("postgres-outage.docx");
  docker(...compose, "stop", "postgres");
  docker("start", "argus-validation-document-worker-1");
  const unavailable = await request(`/documents/${postgresId}`);
  assert.equal(unavailable.status, 503);
  await sleep(6000);
  docker(...compose, "start", "postgres");
  await waitFor(postgresId, "ready");
  console.log("PASS PostgreSQL stopped: API returned 503; committed upload survived restart");
} finally {
  try { docker(...compose, "unpause", "clamav"); } catch {}
  docker("start", "argus-validation-postgres-1", "argus-validation-redis-1", "argus-validation-clamav-1", "argus-validation-document-worker-1");
  await sleep(3000);
  fixture("cleanup", account.id);
}
