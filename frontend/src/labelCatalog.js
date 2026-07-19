function searchable(value) {
  return String(value ?? "")
    .toLowerCase()
    .replaceAll("×", "x")
    .replace(/[^a-z0-9.]+/g, " ")
    .trim();
}

export function filterLabels(labels, query, filters = {}) {
  const terms = searchable(query).split(/\s+/).filter(Boolean);
  return labels.filter((label) => {
    if (filters.form && label.form_code !== filters.form) return false;
    if (filters.manufacturer && label.manufacturer !== filters.manufacturer) return false;
    if (filters.size && label.size_key !== filters.size) return false;
    if (filters.inStock && Number(label.remaining || 0) <= 0) return false;

    const text = searchable(
      `${label.manufacturer} ${label.paper_line} ${label.form} ${label.form_code} ${label.size_label} ${label.item_name} ${label.item_code} ${label.label_code} ${label.tracking} ${label.stock_uom}`,
    );
    const compact = text.replaceAll(" ", "");
    return terms.every((term) => text.includes(term) || compact.includes(term));
  });
}

const FORM_ORDER = { R: 0, S: 1, C: 2 };
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });

function compareText(left, right) {
  return collator.compare(String(left ?? ""), String(right ?? ""));
}

function sortableDimension(value) {
  if (value === null || value === undefined || value === "") return Infinity;
  const number = Number(value);
  return Number.isFinite(number) ? number : Infinity;
}

function compareSize(left, right) {
  const leftWidth = sortableDimension(left.size_width);
  const rightWidth = sortableDimension(right.size_width);
  if (leftWidth !== rightWidth) return leftWidth - rightWidth;
  const leftHeight = sortableDimension(left.size_height);
  const rightHeight = sortableDimension(right.size_height);
  return leftHeight - rightHeight;
}

export function sortLabels(labels, sort = "size") {
  return [...labels].sort((left, right) => {
    if (sort === "barcode") {
      return compareText(left.label_code, right.label_code) || compareText(left.item_code, right.item_code);
    }
    if (sort === "name") {
      return compareText(left.paper_line, right.paper_line)
        || compareText(left.manufacturer, right.manufacturer)
        || compareSize(left, right)
        || compareText(left.item_code, right.item_code);
    }
    if (sort === "manufacturer") {
      return compareText(left.manufacturer, right.manufacturer)
        || compareText(left.paper_line, right.paper_line)
        || compareSize(left, right)
        || compareText(left.item_code, right.item_code);
    }
    return (FORM_ORDER[left.form_code] ?? 99) - (FORM_ORDER[right.form_code] ?? 99)
      || compareSize(left, right)
      || compareText(left.manufacturer, right.manufacturer)
      || compareText(left.paper_line, right.paper_line)
      || compareText(left.item_code, right.item_code);
  });
}

const FORM_GROUPS = [
  { key: "R", label: "Rolls" },
  { key: "S", label: "Sheets" },
  { key: "C", label: "Cards" },
];

export function groupLabels(labels, groupBy = "form") {
  if (groupBy === "none") return [{ key: "all", label: "All labels", labels }];
  if (groupBy === "manufacturer") {
    const manufacturers = [...new Set(labels.map((label) => label.manufacturer || "Unspecified"))].sort(compareText);
    return manufacturers.map((manufacturer) => ({
      key: manufacturer,
      label: manufacturer,
      labels: labels.filter((label) => (label.manufacturer || "Unspecified") === manufacturer),
    }));
  }
  return FORM_GROUPS.map((group) => ({
    ...group,
    labels: labels.filter((label) => label.form_code === group.key),
  })).filter((group) => group.labels.length);
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
