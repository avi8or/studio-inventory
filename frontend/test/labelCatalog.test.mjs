import assert from "node:assert/strict";
import test from "node:test";

import { filterLabels, toggleVisibleSelection } from "../src/labelCatalog.js";

const LABELS = [
  {
    item_name: "Red River Paper — UltraPro Satin 270 — 13 × 19 in",
    item_code: "P-RR-ULTRAPRO-SATIN-270-S-13X19",
    label_code: "INV000001",
    has_internal_barcode: true,
    tracking: "Item",
    stock_uom: "Sheet",
  },
  {
    item_name: "Hahnemühle Photo Rag Roll",
    item_code: "P-HAHN-PHOTORAG-R-24",
    label_code: "INV000002",
    has_internal_barcode: true,
    tracking: "Item",
    stock_uom: "Foot",
  },
  {
    item_name: "Hahnemühle — Torchon — 285 GSM — 24 in roll",
    item_code: "P-HAHN-TORCHON-285-R-24",
    label_code: "INV000003",
    has_internal_barcode: true,
    tracking: "Item",
    stock_uom: "Foot",
  },
];

test("searches reusable Item labels by words, compact size, SKU, and stock UOM", () => {
  assert.deepEqual(filterLabels(LABELS, "red satin 13x19"), [LABELS[0]]);
  assert.deepEqual(filterLabels(LABELS, "photo rag foot"), [LABELS[1]]);
  assert.deepEqual(filterLabels(LABELS, "ultrapro-satin"), [LABELS[0]]);
  assert.deepEqual(filterLabels(LABELS, "torchon 24 item"), [LABELS[2]]);
  assert.deepEqual(filterLabels(LABELS, "inv000003"), [LABELS[2]]);
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
