import assert from "node:assert/strict";
import test from "node:test";

import {
  buyingPriceFor,
  formatRequiredFields,
  missingReceiveFields,
} from "../src/receiveForm.js";

const purchaseUoms = [
  { uom: "Foot", conversion_factor: 1 },
  { uom: "Roll 39.37 Foot", conversion_factor: 39.37 },
];

test("names every incomplete Receive field", () => {
  assert.deepEqual(missingReceiveFields({
    warehouse: "Stores - LPS",
    supplier: "",
    purchaseUom: "Roll 39.37 Foot",
    purchaseUnits: 1,
    unitCost: null,
  }), ["Supplier", "Unit cost"]);

  assert.equal(
    formatRequiredFields(["Supplier", "Unit cost"]),
    "Supplier and Unit cost",
  );
});

test("rejects invalid purchase counts and costs", () => {
  assert.deepEqual(missingReceiveFields({
    warehouse: "",
    supplier: "B&H Photo Video",
    purchaseUom: "",
    purchaseUnits: 1.5,
    unitCost: -1,
  }), ["Warehouse", "Purchase unit", "Number of purchase units", "Unit cost"]);
});

test("prefers an exact supplier and UOM buying price", () => {
  const price = buyingPriceFor({
    buyingPrices: [
      { supplier: "", uom: "Foot", stock_rate: 9, price_list: "Standard Buying" },
      { supplier: "B&H Photo Video", uom: "Roll 39.37 Foot", stock_rate: 257.99 / 39.37 },
    ],
    purchaseUoms,
    supplier: "B&H Photo Video",
    purchaseUom: "Roll 39.37 Foot",
  });

  assert.equal(price.suggested_unit_cost, 257.99);
  assert.equal(price.supplier, "B&H Photo Video");
});

test("converts a supplier buying price from stock UOM to the selected package", () => {
  const price = buyingPriceFor({
    buyingPrices: [
      { supplier: "Breathing Color", uom: "Foot", stock_rate: 2.5 },
    ],
    purchaseUoms,
    supplier: "Breathing Color",
    purchaseUom: "Roll 39.37 Foot",
  });

  assert.equal(price.suggested_unit_cost, 98.43);
});

test("does not borrow another supplier's price", () => {
  assert.equal(buyingPriceFor({
    buyingPrices: [{ supplier: "Red River", uom: "Foot", stock_rate: 2.5 }],
    purchaseUoms,
    supplier: "B&H Photo Video",
    purchaseUom: "Roll 39.37 Foot",
  }), null);
});
