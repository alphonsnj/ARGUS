import assert from "node:assert/strict";
import { serializeRuntimeEnv } from "./runtime-env.mjs";

assert.equal(serializeRuntimeEnv({ S3_ENDPOINT_URL: "http://minio:9000" }),
  "S3_ENDPOINT_URL='http://minio:9000'\n");
assert.equal(serializeRuntimeEnv({ SECRET: "a'b$literal" }), "SECRET='a\\'b$literal'\n");
for (const values of [{ BAD: "one\ntwo" }, { "BAD=KEY": "x" }, { BAD: null }]) {
  assert.throws(() => serializeRuntimeEnv(values));
}
console.log("PASS private runtime env serialization");
