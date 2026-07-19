import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const barcodeComponent = await readFile(new URL("../src/BarcodeSvg.vue", import.meta.url), "utf8");
const stylesheet = await readFile(new URL("../src/index.css", import.meta.url), "utf8");

test("printed inventory barcodes have quiet zones and a uniform box", () => {
  assert.match(barcodeComponent, /marginLeft: 15,[\s\S]*marginRight: 15,/);
  assert.match(
    stylesheet,
    /\.print-label-card \.barcode-wrap svg \{[\s\S]*width: 3\.15in;[\s\S]*height: 0\.55in;/,
  );
});
