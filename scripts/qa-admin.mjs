import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "@playwright/test";

// Production-built UI against synthetic API responses; never uses real accounts.
const server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "apps/web", "-p", "3101"], { stdio: "ignore" });
let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 80; attempt++) {
    if (server.exitCode !== null) throw new Error("UI test server exited");
    try { ready = (await fetch("http://localhost:3101/sign-in")).ok; } catch { /* startup */ }
    if (ready) break;
    await delay(250);
  }
  assert.ok(ready, "UI test server did not become ready");
  browser = await chromium.launch({ channel: process.env.CI ? undefined : "chrome", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(() => sessionStorage.setItem("argus_access_token", "synthetic-ui-token"));
  const admin = { id: "admin", email: "admin@example.com", roles: ["Super Administrator"], is_active: true, mfa_enabled: false };
  const other = { ...admin, id: "other", email: "other@example.com", roles: ["Analyst"] };
  let restricted = false;
  let unavailable = false;
  let revocations = 0;
  let logoutAll = 0;
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    const endpoint = url.pathname;
    if (endpoint.endsWith("/users/me")) return route.fulfill({ json: restricted ? other : admin });
    if (endpoint.endsWith("/users")) return route.fulfill({ status: restricted ? 403 : 200, json: restricted ? {} : [admin, other] });
    if (endpoint.endsWith("/audit")) {
      assert.equal(url.searchParams.get("limit"), "100");
      if (unavailable) return route.abort();
      return route.fulfill({ status: restricted ? 403 : 200, json: restricted ? {} : [{
        id: "event", created_at: "2026-10-03T00:00:00Z", action: "session.revoked",
        actor_id: "admin", subject_id: "other", request_id: "request-123",
      }] });
    }
    if (endpoint.endsWith("/users/other/sessions")) {
      assert.equal(route.request().method(), "DELETE");
      revocations++;
      return route.fulfill({ status: unavailable ? 503 : 204 });
    }
    if (endpoint.endsWith("/auth/logout-all")) {
      assert.equal(route.request().method(), "POST");
      logoutAll++;
      return route.fulfill({ status: 204 });
    }
    return route.fulfill({ status: 401, json: {} });
  });
  await page.goto("http://localhost:3101/dashboard/users");
  const revoke = page.getByRole("button", { name: "Revoke sessions for other@example.com" });
  await revoke.waitFor();
  page.once("dialog", dialog => dialog.dismiss());
  await revoke.click();
  assert.equal(revocations, 0, "Cancellation must not send a request");
  unavailable = true;
  page.once("dialog", dialog => dialog.accept());
  await revoke.click();
  await page.getByText("Sign-out could not be confirmed. Please try again.", { exact: true }).waitFor();
  unavailable = false;
  page.once("dialog", dialog => dialog.accept());
  await revoke.click();
  await page.getByText("Sessions revoked for other@example.com. A new login is still allowed.", { exact: true }).waitFor();
  assert.equal(revocations, 2);
  await page.getByRole("link", { name: "Audit history" }).click();
  await page.getByText("session.revoked", { exact: true }).waitFor();
  unavailable = true;
  await page.getByRole("button", { name: "Refresh history" }).click();
  await page.getByText("Audit history could not be refreshed. Check the connection and try again.", { exact: true }).waitFor();
  unavailable = false;
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: "/tmp/argus-admin-mobile.png", fullPage: true });
  restricted = true;
  await page.reload();
  await page.getByText("Audit history is restricted to Super Administrators.", { exact: true }).waitFor();
  assert.equal(await page.getByRole("link", { name: "Audit history" }).count(), 0);
  await page.goto("http://localhost:3101/dashboard/users");
  await page.getByText("Your role can view your profile but cannot list platform users.", { exact: true }).waitFor();
  assert.equal(await page.getByRole("button", { name: /Revoke sessions for/ }).count(), 0);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Sign out everywhere" }).click();
  await page.waitForURL("**/sign-in");
  assert.equal(logoutAll, 1);
  assert.equal(await page.evaluate(() => sessionStorage.getItem("argus_access_token")), null);
  assert.deepEqual(errors, []);
  console.log("PASS admin UI: confirmation/cancel, errors, revoke, audit, role boundaries, mobile and logout-all");
} finally {
  if (browser) await browser.close();
  server.kill("SIGTERM");
}
