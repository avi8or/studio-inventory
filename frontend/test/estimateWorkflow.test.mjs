import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const calculator = readFileSync(new URL("../src/PriceCalculator.vue", import.meta.url), "utf8");
const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8");
const estimateDialog = readFileSync(
  new URL("../../studio_inventory/public/js/quotation.js", import.meta.url),
  "utf8",
);

test("a calculator opened from an Estimate Request can start a native Estimate", () => {
  assert.match(app, /searchParams\.get\("estimate_request"\)/);
  assert.match(app, /:estimate-request="estimateRequest"/);
  assert.match(calculator, /create_estimate/);
  assert.match(calculator, /crm_deal: props\.estimateRequest/);
  assert.match(calculator, /Start Estimate/);
});

test("the calculator distinguishes pricing paper from loaded stock", () => {
  assert.match(calculator, /Pricing paper basis/);
  assert.match(calculator, /pricing_cost_source/);
});

test("paper selection chooses a family before an exact stock variant", () => {
  assert.match(calculator, /context\.value\?\.paper_catalog/);
  assert.match(calculator, /Paper type/);
  assert.match(calculator, /Stock size \/ form/);
  assert.match(calculator, /selectedPaperFamily\?\.variants/);
  assert.match(calculator, /v-model="form\.paper_item"/);

  assert.match(estimateDialog, /fieldname: "paper_family"/);
  assert.match(estimateDialog, /fieldname: "paper_variant"/);
  assert.match(estimateDialog, /paper_item: variant\.name/);
});
