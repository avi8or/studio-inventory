import assert from "node:assert/strict";
import test from "node:test";

import { filterLabels, toggleVisibleSelection } from "../src/labelCatalog.js";

const LABELS = [
  {
    item_name: "Red River Paper — UltraPro Satin 270 — 13 × 19 in",
    item_code: "P-RR-ULTRAPRO-SATIN-270-S-13X19",
    label_code: "P-RR-ULTRAPRO-SATIN-270-S-13X19",
    tracking: "Item",
    stock_uom: "Sheet",
  },
  {
    item_name: "Hahnemühle Photo Rag Roll",
    item_code: "P-HAHN-PHOTORAG-R-24",
    label_code: "SIB.000123",
    tracking: "Batch",
    stock_uom: "Foot",
  },
  {
    item_name: "Hahnemühle — Torchon — 285 GSM — 24 in roll",
    item_code: "P-HAHN-TORCHON-285-R-24",
    label_code: "P-HAHN-TORCHON-285-R-24",
    tracking: "Item",
    stock_uom: "Foot",
    receive_only: true,
  },
];

test("searches labels by words, compact size, SKU, and Batch", () => {
  assert.deepEqual(filterLabels(LABELS, "red satin 13x19"), [LABELS[0]]);
  assert.deepEqual(filterLabels(LABELS, "photo rag SIB.000123"), [LABELS[1]]);
  assert.deepEqual(filterLabels(LABELS, "ultrapro-satin"), [LABELS[0]]);
  assert.deepEqual(filterLabels(LABELS, "torchon 24 receive"), [LABELS[2]]);
});

test("selects and clears only the visible search results", () => {
  assert.deepEqual(toggleVisibleSelection([LABELS[1].label_code], [LABELS[0]]), [
    LABELS[1].label_code,
    LABELS[0].label_code,
  ]);
  assert.deepEqual(
    toggleVisibleSelection(
      [LABELS[1].label_code, LABELS[0].label_code],
      [LABELS[0]],
    ),
    [LABELS[1].label_code],
  );
});
