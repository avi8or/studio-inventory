import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const calculator = readFileSync(new URL("../src/PriceCalculator.vue", import.meta.url), "utf8");
const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8");

test("a calculator opened from an Estimate Request can start a native Estimate", () => {
  assert.match(app, /searchParams\.get\("estimate_request"\)/);
  assert.match(app, /:estimate-request="estimateRequest"/);
  assert.match(calculator, /create_estimate/);
  assert.match(calculator, /crm_deal: props\.estimateRequest/);
  assert.match(calculator, /Start Estimate/);
});
