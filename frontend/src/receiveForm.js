export function missingReceiveFields(form) {
  const missing = [];
  const purchaseUnits = Number(form.purchaseUnits);
  const unitCost = Number(form.unitCost);

  if (!form.warehouse) missing.push("Warehouse");
  if (!form.supplier) missing.push("Supplier");
  if (!form.purchaseUom) missing.push("Purchase unit");
  if (!Number.isInteger(purchaseUnits) || purchaseUnits < 1) {
    missing.push("Number of purchase units");
  }
  if (
    form.unitCost === null
    || form.unitCost === ""
    || !Number.isFinite(unitCost)
    || unitCost < 0
  ) {
    missing.push("Unit cost");
  }
  return missing;
}

export function formatRequiredFields(fields) {
  if (fields.length < 2) return fields[0] || "";
  if (fields.length === 2) return `${fields[0]} and ${fields[1]}`;
  return `${fields.slice(0, -1).join(", ")}, and ${fields.at(-1)}`;
}

export function buyingPriceFor({ buyingPrices, purchaseUoms, supplier, purchaseUom }) {
  if (!supplier || !purchaseUom) return null;
  const conversionFactor = Number(
    purchaseUoms.find((row) => row.uom === purchaseUom)?.conversion_factor,
  );
  if (!Number.isFinite(conversionFactor) || conversionFactor <= 0) return null;

  const supplierPrices = buyingPrices.filter((price) => price.supplier === supplier);
  const generalPrices = buyingPrices.filter((price) => !price.supplier);
  const candidates = supplierPrices.length ? supplierPrices : generalPrices;
  const price = candidates.find((candidate) => candidate.uom === purchaseUom) || candidates[0];
  const stockRate = Number(price?.stock_rate);
  if (!price || !Number.isFinite(stockRate) || stockRate < 0) return null;

  return {
    ...price,
    suggested_unit_cost: Math.round(stockRate * conversionFactor * 100) / 100,
  };
}
