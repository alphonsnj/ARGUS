// Local image inventory. Nonzero exit means findings OR incomplete scanning.
import { spawnSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const directory = path.resolve("backups", `security-${new Date().toISOString().replaceAll(":", "-")}`);
await mkdir(directory, { recursive: true, mode: 0o700 });
const images = process.argv.slice(2);
if (!images.length) {
  const configured = spawnSync("docker", ["compose", "config", "--images"], { encoding: "utf8" });
  if (configured.status !== 0) throw new Error("Could not resolve configured image inventory");
  images.push(...new Set(configured.stdout.trim().split(/\s+/).filter(Boolean)));
  if (!images.length) throw new Error("No configured images to scan");
}
const results = [];
for (const [index, image] of images.entries()) {
  const inspect = spawnSync("docker", ["image", "inspect", image, "--format", "{{.Id}}"], { encoding: "utf8" });
  if (inspect.status !== 0) {
    results.push({ image, error: "Image unavailable locally; build/pull it first" });
    process.exitCode = 1;
    continue;
  }
  const id = inspect.stdout.trim();
  const file = `${index}.json`;
  const scan = spawnSync("docker", ["run", "--rm",
    "-v", "/var/run/docker.sock:/var/run/docker.sock", "-v", "argus-trivy-cache:/root/.cache/",
    "-v", `${directory}:/reports`, "aquasec/trivy:0.69.3", "image", "--quiet",
    "--scanners", "vuln", "--severity", "HIGH,CRITICAL", "--format", "json",
    "--output", `/reports/${file}`, id], { stdio: "inherit" });
  if (scan.status !== 0) {
    results.push({ image, id, error: "Scanner failed; result is NOT clean" });
    process.exitCode = 1;
    continue;
  }
  const report = JSON.parse(await readFile(path.join(directory, file), "utf8"));
  const findings = (report.Results || []).flatMap(result => result.Vulnerabilities || []);
  const result = { image, id, file, highCritical: findings.length,
    withFix: findings.filter(finding => finding.FixedVersion).length };
  results.push(result);
  console.log(JSON.stringify(result));
  if (findings.length) process.exitCode = 1;
}
await writeFile(path.join(directory, "summary.json"), JSON.stringify({
  scannedAt: new Date().toISOString(), scanner: "aquasec/trivy:0.69.3", results,
}, null, 2), { mode: 0o600 });
console.log(`Reports: ${directory}`);
