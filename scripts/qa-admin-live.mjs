import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { chromium } from "@playwright/test";

// Uses disposable identities only. Never prints credentials or session tokens.
const fixture = (...args) => execFileSync("docker", ["run", "--rm", "--network", "argus_default", "--env-file", ".env", "-v", `${process.cwd()}/scripts:/qa:ro`, "--entrypoint", "python", "argus-api", "/qa/qa_fixture.py", ...args], { encoding: "utf8" });
const accounts = [];
let browser;
try {
  const admin = JSON.parse(fixture("seed", "--admin"));
  accounts.push(admin.id);
  const other = JSON.parse(fixture("seed"));
  accounts.push(other.id);
  browser = await chromium.launch({ channel: "chrome", headless: true });
  const adminContext = await browser.newContext();
  const otherContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  const otherPage = await otherContext.newPage();
  const errors = [];
  for (const page of [adminPage, otherPage]) page.on("pageerror", error => errors.push(error.message));
  async function login(page, account) {
    await page.goto("http://localhost:3000/sign-in");
    await page.getByLabel("Work email").fill(account.email);
    await page.getByLabel("Password", { exact: true }).fill(account.password);
    await page.getByRole("button", { name: "Verify access" }).click();
    await page.waitForURL("**/dashboard");
    return page.evaluate(() => sessionStorage.getItem("argus_access_token"));
  }
  const adminToken = await login(adminPage, admin);
  const otherToken = await login(otherPage, other);
  const authenticated = (context, token, path) => context.request.get(`http://localhost:8000/api/v1${path}`, { headers: { Authorization: `Bearer ${token}` } });
  assert.equal((await authenticated(otherContext, otherToken, "/audit")).status(), 403);
  await adminPage.getByRole("link", { name: "Users", exact: true }).click();
  adminPage.once("dialog", dialog => dialog.accept());
  await adminPage.getByRole("button", { name: `Revoke sessions for ${other.email}` }).click();
  await adminPage.getByText(`Sessions revoked for ${other.email}. A new login is still allowed.`, { exact: true }).waitFor();
  assert.equal((await authenticated(otherContext, otherToken, "/users/me")).status(), 401);
  await otherPage.reload();
  await otherPage.waitForURL("**/sign-in");
  await adminPage.getByRole("link", { name: "Audit history" }).click();
  const event = adminPage.getByRole("row").filter({ hasText: other.id }).filter({ hasText: "sessions.revoked" });
  await event.first().waitFor();
  await adminPage.getByRole("link", { name: "Users", exact: true }).click();
  adminPage.once("dialog", dialog => dialog.accept());
  await adminPage.getByRole("button", { name: "Sign out everywhere" }).click();
  await adminPage.waitForURL("**/sign-in");
  assert.equal((await authenticated(adminContext, adminToken, "/users/me")).status(), 401);
  assert.deepEqual(errors, []);
  console.log("PASS live admin: login, revoke another session, old-token denial, audit record, role denial and logout-all");
} finally {
  if (browser) await browser.close();
  for (const id of accounts) fixture("cleanup", id);
}
