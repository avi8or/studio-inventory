import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const stylesheet = await readFile(new URL("../src/index.css", import.meta.url), "utf8");
const priceCalculator = await readFile(new URL("../src/PriceCalculator.vue", import.meta.url), "utf8");

test("mobile and touch form controls avoid Safari focus zoom", () => {
  assert.match(
    stylesheet,
    /@media \(max-width: 900px\), \(any-pointer: coarse\) \{[\s\S]*?input:not\(\[type="checkbox"\]\):not\(\[type="radio"\]\),[\s\S]*?select:not\(:disabled\),[\s\S]*?textarea:not\(:disabled\) \{[\s\S]*?font-size: 16px;/,
  );
});

test("the price calculator uses a bounded custom paper picker instead of a native datalist", () => {
  assert.doesNotMatch(priceCalculator, /<datalist\b/);
  assert.match(priceCalculator, /role="combobox"/);
  assert.match(priceCalculator, /role="listbox"/);
  assert.match(priceCalculator, /searchPaperOptions/);
});

test("paper results and calculator controls have mobile touch targets", () => {
  assert.match(stylesheet, /\.paper-option \{[\s\S]*?min-height: 48px;/);
  assert.match(
    stylesheet,
    /@media \(max-width: 639px\) \{[\s\S]*?\.price-page \.field input,[\s\S]*?min-height: 44px;[\s\S]*?\.paper-option \{[\s\S]*?min-height: 52px;/,
  );
});
