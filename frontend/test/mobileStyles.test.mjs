import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const stylesheet = await readFile(new URL("../src/index.css", import.meta.url), "utf8");

test("mobile and touch form controls avoid Safari focus zoom", () => {
  assert.match(
    stylesheet,
    /@media \(max-width: 900px\), \(any-pointer: coarse\) \{[\s\S]*?input:not\(\[type="checkbox"\]\):not\(\[type="radio"\]\),[\s\S]*?select,[\s\S]*?textarea \{[\s\S]*?font-size: 16px;/,
  );
});
