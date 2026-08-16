export const PAPER_OPTION_LIMIT = 40;

function normalize(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase()
    .replace(/œ/g, "oe")
    .replace(/æ/g, "ae")
    .replace(/ø/g, "o")
    .replace(/ß/g, "ss")
    .replace(/[®™℠]/g, " ")
    .replace(/×/g, " x ")
    .replace(/(\d)\s*x\s*(?=\d)/g, "$1x")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function tokens(value) {
  return normalize(value).split(" ").filter(Boolean);
}

function editDistance(left, right) {
  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let leftIndex = 0; leftIndex < left.length; leftIndex += 1) {
    const current = [leftIndex + 1];
    for (let rightIndex = 0; rightIndex < right.length; rightIndex += 1) {
      current.push(Math.min(
        current[rightIndex] + 1,
        previous[rightIndex + 1] + 1,
        previous[rightIndex] + (left[leftIndex] === right[rightIndex] ? 0 : 1),
      ));
    }
    previous = current;
  }
  return previous[right.length];
}

function tokenMatchScore(queryToken, candidateToken) {
  if (queryToken === candidateToken) return 100;
  if (queryToken.length >= 2 && candidateToken.startsWith(queryToken)) return 80;
  if (queryToken.length >= 3 && candidateToken.includes(queryToken)) return 70;

  const allowedDistance = queryToken.length >= 7 ? 2 : queryToken.length >= 4 ? 1 : 0;
  if (!allowedDistance || Math.abs(queryToken.length - candidateToken.length) > allowedDistance) return 0;
  const distance = editDistance(queryToken, candidateToken);
  return distance <= allowedDistance ? 60 - distance * 5 : 0;
}

function fieldTokenScore(queryToken, field) {
  let best = 0;
  for (const candidateToken of field.tokens) {
    best = Math.max(best, tokenMatchScore(queryToken, candidateToken));
  }
  return best ? best + field.weight : 0;
}

function matchScore(entry, query) {
  const queryTokens = tokens(query);
  if (!queryTokens.length) return 0;

  let matched = 0;
  let score = 0;
  for (const queryToken of queryTokens) {
    const tokenScore = Math.max(...entry.fields.map((field) => fieldTokenScore(queryToken, field)));
    if (!tokenScore) continue;
    matched += 1;
    score += tokenScore;
  }

  if (matched < Math.ceil(queryTokens.length / 2)) return null;
  score += matched * 1000 - (queryTokens.length - matched) * 150;
  if (matched === queryTokens.length) score += 300;
  if (entry.name.startsWith(query)) score += 200;
  else if (entry.name.includes(query)) score += 100;
  if (entry.code === query) score += 300;
  return score;
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
      fields: [
        { tokens: tokens(item.item_name), weight: 30 },
        { tokens: tokens(item.brand), weight: 25 },
        { tokens: tokens(item.name), weight: 20 },
        { tokens: tokens(item.stock_uom), weight: 5 },
      ],
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

  const matches = index
    .map((entry) => ({ entry, score: matchScore(entry, search) }))
    .filter(({ score }) => score !== null)
    .sort((left, right) => (
      right.score - left.score
      || left.entry.name.localeCompare(right.entry.name)
      || left.entry.code.localeCompare(right.entry.code)
    ));

  return {
    options: matches.slice(0, limit).map(({ entry }) => entry.item),
    total: matches.length,
  };
}
