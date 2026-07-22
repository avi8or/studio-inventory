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

test("the price action and total stay outside the scrolling workspace", () => {
  const workspaceEnd = priceCalculator.lastIndexOf("</aside>\n    </div>");
  const actionBar = priceCalculator.indexOf('class="price-action-bar"');

  assert.ok(workspaceEnd >= 0);
  assert.ok(actionBar > workspaceEnd);
  assert.match(priceCalculator, /<form id="price-calculator-form"/);
  assert.match(priceCalculator, /form="price-calculator-form"/);
  assert.match(stylesheet, /\.price-action-bar \{[\s\S]*?flex: 0 0 auto;[\s\S]*?env\(safe-area-inset-bottom/);
});

test("changed inputs invalidate an existing price and validation stays inline", () => {
  assert.match(priceCalculator, /watch\(form,[\s\S]*?result\.value = null;[\s\S]*?resultStale\.value = true;/);
  assert.match(priceCalculator, /novalidate @submit\.prevent="calculate"/);
  assert.match(priceCalculator, /validationErrorsForForm/);
  assert.match(priceCalculator, /class="field-error"/);
  assert.doesNotMatch(priceCalculator, /setCustomValidity/);
});

test("blank optional calculator values are sent as zero", () => {
  assert.match(priceCalculator, /function zeroWhenBlank\(value\)/);
  assert.match(priceCalculator, /border_in: zeroWhenBlank\(form\.border_in\)/);
  assert.match(priceCalculator, /time_minutes: zeroWhenBlank\(form\.time_minutes\)/);
  assert.match(priceCalculator, /ink_cost_per_sq_in: zeroWhenBlank\(form\.ink_cost_per_sq_in\)/);
  assert.match(priceCalculator, /payload: calculationPayload\(\)/);
  assert.doesNotMatch(priceCalculator, /cost_override: zeroWhenBlank/);
});

test("the paper picker starts with device-local recents and waits for a useful query", () => {
  assert.match(priceCalculator, /RECENT_PAPER_LIMIT = 5/);
  assert.match(priceCalculator, /localStorage\.setItem\(RECENT_PAPER_KEY/);
  assert.match(priceCalculator, /Type at least 2 characters to search/);
  assert.match(priceCalculator, /Recent papers/);
});

test("mobile costing and result details use compact disclosures", () => {
  assert.match(priceCalculator, /class="price-mobile-section-toggle"/);
  assert.match(priceCalculator, /class="price-breakdown-link"/);
  assert.match(priceCalculator, /'mobile-open': resultBreakdownOpen/);
  assert.match(stylesheet, /\.price-results\.mobile-open \{[\s\S]*?position: fixed;[\s\S]*?max-height: 78dvh;/);
});

test("the calculator includes size shortcuts and a tighter desktop result layout", () => {
  assert.match(priceCalculator, /SIZE_PRESETS/);
  assert.match(priceCalculator, /swapArtworkDimensions/);
  assert.match(priceCalculator, /class="price-result-paper"/);
  assert.match(priceCalculator, /printCount\(result\.calculation\.quantity\)/);
  assert.match(priceCalculator, /Number\(result\.calculation\.quantity\) > 1/);
  assert.match(stylesheet, /\.price-workspace \{[\s\S]*?max-width: 1300px;[\s\S]*?margin: 0 auto;/);
  assert.match(stylesheet, /\.filter-row\.price-heading \{[\s\S]*?flex-direction: row;/);
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
