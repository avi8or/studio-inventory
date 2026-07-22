import assert from "node:assert/strict";
import test from "node:test";

import {
  PAPER_OPTION_LIMIT,
  buildPaperSearchIndex,
  searchPaperOptions,
} from "../src/paperSearch.js";

test("paper search matches names, Item codes, and brands without case sensitivity", () => {
  const index = buildPaperSearchIndex([
    { name: "PAPER-001", item_name: "Hahnemühle Photo Rag", brand: "Hahnemühle" },
    { name: "ARCHES-BFK", item_name: "BFK Rives", brand: "Arches" },
  ]);

  assert.deepEqual(searchPaperOptions(index, "photo").options.map((item) => item.name), ["PAPER-001"]);
  assert.deepEqual(searchPaperOptions(index, "arches").options.map((item) => item.name), ["ARCHES-BFK"]);
  assert.deepEqual(searchPaperOptions(index, "paper-001").options.map((item) => item.name), ["PAPER-001"]);
});

test("paper search ranks prefix matches ahead of contains matches", () => {
  const index = buildPaperSearchIndex([
    { name: "Z-ARCHES", item_name: "Heavy Arches paper" },
    { name: "A-ARCHES", item_name: "Arches BFK Rives" },
  ]);

  assert.deepEqual(searchPaperOptions(index, "arches").options.map((item) => item.name), [
    "A-ARCHES",
    "Z-ARCHES",
  ]);
});

test("paper search reports every match but bounds the rendered result set", () => {
  const papers = Array.from({ length: PAPER_OPTION_LIMIT + 15 }, (_, index) => ({
    name: `PAPER-${index}`,
    item_name: `Paper ${index}`,
  }));

  const result = searchPaperOptions(buildPaperSearchIndex(papers), "paper");

  assert.equal(result.total, papers.length);
  assert.equal(result.options.length, PAPER_OPTION_LIMIT);
});
