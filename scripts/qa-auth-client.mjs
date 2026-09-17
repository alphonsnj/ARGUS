import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

// Contract-test concurrent 401 recovery without real credentials/network calls.
const source = await readFile("apps/web/src/lib/api.ts", "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022,
} }).outputText;
const values = new Map([["argus_access_token", "expired-test-token"]]);
globalThis.sessionStorage = { getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value) };
let rotations = 0;
globalThis.fetch = async (url, options) => {
  if (url.endsWith("/auth/refresh")) {
    rotations++;
    await new Promise(resolve => setTimeout(resolve, 10));
    return Response.json({ access_token: "new-test-token" });
  }
  return new Response(null, {
    status: options.headers.Authorization === "Bearer new-test-token" ? 200 : 401,
  });
};
const { apiFetch } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
const responses = await Promise.all(Array.from({ length: 20 }, () => apiFetch("/documents")));
assert.ok(responses.every(response => response.status === 200));
assert.equal(rotations, 1);
console.log("PASS: 20 concurrent unauthorized requests share one refresh rotation");
