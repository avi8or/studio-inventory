function searchable(value) {
  return String(value ?? "")
    .toLowerCase()
    .replaceAll("×", "x")
    .replace(/[^a-z0-9.]+/g, " ")
    .trim();
}

export function filterLabels(labels, query) {
  const terms = searchable(query).split(/\s+/).filter(Boolean);
  if (!terms.length) return labels;

  return labels.filter((label) => {
    const text = searchable(
      `${label.item_name} ${label.item_code} ${label.label_code} ${label.tracking} ${label.stock_uom}`,
    );
    const compact = text.replaceAll(" ", "");
    return terms.every((term) => text.includes(term) || compact.includes(term));
  });
}

export function toggleVisibleSelection(selectedCodes, visibleLabels) {
  const visibleCodes = visibleLabels.map((label) => label.label_code);
  const selected = new Set(selectedCodes);
  const allVisibleSelected = visibleCodes.length > 0 && visibleCodes.every((code) => selected.has(code));

  for (const code of visibleCodes) {
    if (allVisibleSelected) selected.delete(code);
    else selected.add(code);
  }
  return [...selected];
}
