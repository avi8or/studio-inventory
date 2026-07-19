import assert from "node:assert/strict";
import test from "node:test";

import {
  filterLabels,
  groupLabels,
  sortLabels,
  toggleVisibleSelection,
} from "../src/labelCatalog.js";

const LABELS = [
  {
    manufacturer: "Red River Paper",
    paper_line: "UltraPro Satin 270",
    form: "SHEET",
    form_code: "S",
    size_label: "13 × 19\"",
    size_key: "13x19",
    size_width: 13,
    size_height: 19,
    item_name: "Red River Paper — UltraPro Satin 270 — 13 × 19 in",
    item_code: "P-RR-ULTRAPRO-SATIN-270-S-13X19",
    label_code: "LP000001",
    has_internal_barcode: true,
    tracking: "Item",
    stock_uom: "Sheet",
    remaining: 0,
  },
  {
    manufacturer: "Hahnemühle",
    paper_line: "Photo Rag 308",
    form: "ROLL",
    form_code: "R",
    size_label: "36\"",
    size_key: "36",
    size_width: 36,
    size_height: null,
    item_name: "Hahnemühle Photo Rag Roll",
    item_code: "P-HAHN-PHOTORAG-R-36",
    label_code: "LP000002",
    has_internal_barcode: true,
    tracking: "Item",
    stock_uom: "Foot",
    remaining: 8,
  },
  {
    manufacturer: "Hahnemühle",
    paper_line: "Torchon 285",
    form: "ROLL",
    form_code: "R",
    size_label: "24\"",
    size_key: "24",
    size_width: 24,
    size_height: null,
    item_name: "Hahnemühle — Torchon — 285 GSM — 24 in roll",
    item_code: "P-HAHN-TORCHON-285-R-24",
    label_code: "LP000003",
    has_internal_barcode: true,
    tracking: "Item",
    stock_uom: "Foot",
    remaining: 39,
  },
  {
    manufacturer: "Canson",
    paper_line: "Baryta Photographique II 310",
    form: "SHEET",
    form_code: "S",
    size_label: "8.5 × 11\"",
    size_key: "8.5x11",
    size_width: 8.5,
    size_height: 11,
    item_name: "Canson — Baryta Photographique II 310 — 8.5 × 11 in",
    item_code: "P-CNSN-BARYTA-II-310-S-8.5X11",
    label_code: "LP000004",
    has_internal_barcode: true,
    tracking: "Item",
    stock_uom: "Sheet",
    remaining: 25,
  },
  {
    manufacturer: "Hahnemühle",
    paper_line: "Bamboo 290",
    form: "CARD",
    form_code: "C",
    size_label: "5 × 7\"",
    size_key: "5x7",
    size_width: 5,
    size_height: 7,
    item_name: "Hahnemühle — Bamboo 290 — 5 × 7 in cards",
    item_code: "P-HAHN-BAMBOO-290-C-5X7",
    label_code: "LP000005",
    has_internal_barcode: true,
    tracking: "Item",
    stock_uom: "Card Set",
    remaining: 4,
  },
];

test("searches labels by hierarchy, compact size, SKU, barcode, and form", () => {
  assert.deepEqual(filterLabels(LABELS, "red satin 13x19"), [LABELS[0]]);
  assert.deepEqual(filterLabels(LABELS, "photo rag roll"), [LABELS[1]]);
  assert.deepEqual(filterLabels(LABELS, "ultrapro-satin"), [LABELS[0]]);
  assert.deepEqual(filterLabels(LABELS, "torchon 24 item"), [LABELS[2]]);
  assert.deepEqual(filterLabels(LABELS, "lp000003"), [LABELS[2]]);
});

test("filters by form, manufacturer, size, and positive on-hand balance", () => {
  assert.deepEqual(filterLabels(LABELS, "", { form: "R" }), [LABELS[1], LABELS[2]]);
  assert.deepEqual(filterLabels(LABELS, "", { manufacturer: "Canson" }), [LABELS[3]]);
  assert.deepEqual(filterLabels(LABELS, "", { size: "5x7" }), [LABELS[4]]);
  assert.deepEqual(filterLabels(LABELS, "", { inStock: true }), LABELS.slice(1));
});

test("sorts dimensions numerically and keeps rolls, sheets, and cards together", () => {
  assert.deepEqual(
    sortLabels(LABELS, "size").map((label) => label.label_code),
    ["LP000003", "LP000002", "LP000004", "LP000001", "LP000005"],
  );
});

test("groups labels in roll, sheet, card order", () => {
  const groups = groupLabels(sortLabels(LABELS, "size"), "form");
  assert.deepEqual(groups.map((group) => [group.label, group.labels.length]), [
    ["Rolls", 2],
    ["Sheets", 2],
    ["Cards", 1],
  ]);
});

test("selects and clears only the visible filtered results", () => {
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
