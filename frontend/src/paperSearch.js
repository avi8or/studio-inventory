export const PAPER_OPTION_LIMIT = 40;

function normalize(value) {
  return String(value || "").trim().toLocaleLowerCase();
}

export function buildPaperSearchIndex(items = []) {
  return items.map((item) => {
    const name = normalize(item.item_name);
    const code = normalize(item.name);
    const brand = normalize(item.brand);
    return {
      item,
      name,
      code,
      brand,
      searchable: `${name} ${code} ${brand} ${normalize(item.stock_uom)}`,
    };
  });
}

export function searchPaperOptions(index, query, limit = PAPER_OPTION_LIMIT) {
  const search = normalize(query);
  if (!search) {
    return {
      options: index.slice(0, limit).map((entry) => entry.item),
      total: index.length,
    };
  }

  const prefixMatches = [];
  const containsMatches = [];
  let total = 0;

  for (const entry of index) {
    if (!entry.searchable.includes(search)) continue;
    total += 1;

    const matchesPrefix = entry.name.startsWith(search)
      || entry.code.startsWith(search)
      || entry.brand.startsWith(search);
    const matches = matchesPrefix ? prefixMatches : containsMatches;
    if (matches.length < limit) matches.push(entry.item);
  }

  return {
    options: prefixMatches.concat(containsMatches).slice(0, limit),
    total,
  };
}
