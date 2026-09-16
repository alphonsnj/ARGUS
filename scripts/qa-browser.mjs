import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { chromium } from "@playwright/test";

const fixture = (...args) => execFileSync("docker", ["run", "--rm", "--network", "argus_default", "--env-file", ".env", "-v", `${process.cwd()}/scripts:/qa:ro`, "--entrypoint", "python", "argus-api", "/qa/qa_fixture.py", ...args], { encoding: "utf8" });
const account = JSON.parse(fixture("seed"));
let browser;
try {
  browser = await chromium.launch({ channel: "chrome", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("http://localhost:3000/sign-in");
  await page.getByLabel("Work email").fill(account.email);
  await page.getByLabel("Password", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "Verify access" }).click();
  await page.waitForURL("**/dashboard");
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await page.getByRole("heading", { name: "Documents", exact: true }).waitFor();
  const retryRow = page.locator("article").filter({ hasText: "retry.docx" });
  await retryRow.getByRole("button", { name: "Retry retry.docx" }).click();
  await retryRow.getByRole("status").filter({ hasText: /^ready$/ }).waitFor({ timeout: 60000 });
  await page.getByLabel("Document file").setInputFiles({
    name: "browser-upload.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: Buffer.from(account.file, "base64"),
  });
  await page.getByRole("button", { name: "Start protected intake" }).click();
  const uploaded = page.locator("article").filter({ hasText: "browser-upload.docx" });
  await uploaded.getByRole("status").filter({ hasText: /^ready$/ }).waitFor({ timeout: 60000 });
  await page.getByLabel("Search extracted text").fill("Quasar");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await uploaded.waitFor();
  await page.getByLabel("Search extracted text").fill("nonexistentxyz");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByText("No matching documents.", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Clear search" }).click();
  await uploaded.waitFor();
  await page.screenshot({ path: "/tmp/argus-qa-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "/tmp/argus-qa-mobile.png", fullPage: true });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL("**/sign-in");
  await page.goto("http://localhost:3000/dashboard/documents");
  await page.waitForURL("**/sign-in");
  assert.deepEqual(errors, []);
  console.log("PASS Browser: login, upload, automatic status, search, retry, mobile layout, logout, protected-route redirect; no page errors");
} finally {
  if (browser) await browser.close();
  fixture("cleanup", account.id);
}
