import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

// UI-only contract test: use a disposable local Next server, not real credentials.
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.addInitScript(() => sessionStorage.setItem("argus_access_token", "ui-test-token"));
  const rows = Array.from({ length: 25 }, (_, i) => ({
    id: String(i), original_filename: `evidence-${i}.pdf`, content_type: "application/pdf",
    byte_size: 1000, sha256: "0".repeat(64), status: "ready", entities: [],
    extracted_metadata: {}, failure_reason: null,
    created_at: "2026-09-17T00:00:00Z", updated_at: "2026-09-17T00:00:00Z",
  }));
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/users/me")) {
      await route.fulfill({ json: { id: "test", email: "ui@example.com", is_active: true, roles: [] } });
    } else if (url.pathname.endsWith("/documents")) {
      const offset = Number(url.searchParams.get("offset") || 0);
      const limit = Number(url.searchParams.get("limit") || 50);
      assert.equal(limit, 21);
      const matches = url.searchParams.get("query") ? rows.slice(0, 1) : rows;
      await route.fulfill({ json: matches.slice(offset, offset + limit) });
    } else await route.fulfill({ json: {} });
  });
  await page.goto("http://localhost:3100/dashboard/documents");
  await page.getByText("evidence-0.pdf", { exact: true }).waitFor();
  assert.equal(await page.locator("article").count(), 20);
  assert.ok(await page.getByRole("button", { name: "Previous page" }).isDisabled());
  await page.getByRole("button", { name: "Next page" }).click();
  await page.getByText("evidence-20.pdf", { exact: true }).waitFor();
  assert.equal(await page.locator("article").count(), 5);
  assert.ok(await page.getByRole("button", { name: "Next page" }).isDisabled());
  await page.getByRole("button", { name: "Previous page" }).click();
  await page.getByText("evidence-0.pdf", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Next page" }).click();
  await page.getByText("evidence-20.pdf", { exact: true }).waitFor();
  await page.getByLabel("Search extracted text").fill("evidence");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByText("evidence-0.pdf", { exact: true }).waitFor();
  assert.equal(await page.locator("article").count(), 1);
  assert.ok(await page.getByRole("button", { name: "Previous page" }).isDisabled());
  await page.getByRole("button", { name: "Clear search" }).click();
  await page.getByText("evidence-19.pdf", { exact: true }).waitFor();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  console.log("PASS pagination: 20/5 rows, next/previous bounds, search reset, clear, mobile overflow");
} finally {
  await browser.close();
}
