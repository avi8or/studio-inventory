from __future__ import annotations

import unittest

from studio_inventory.paper_search import normalize_search_text, rank_paper_options


PAPERS = [
	{
		"name": "HAH-PHOTO-RAG-BARYTA",
		"item_name": "Hahnemühle — Photo Rag® Baryta — 315 GSM",
		"brand": "Hahnemühle",
		"stock_uom": "Sheet",
	},
	{
		"name": "HAH-TORCHON",
		"item_name": "Hahnemühle — Torchon — 285 GSM",
		"brand": "Hahnemühle",
		"stock_uom": "Sheet",
	},
	{
		"name": "CANSON-BARYTA",
		"item_name": "Canson — Baryta Photographique II 310",
		"brand": "Canson",
		"stock_uom": "Sheet",
	},
]


class PaperSearchTests(unittest.TestCase):
	def test_normalization_removes_accents_and_trademark_symbols(self):
		self.assertEqual(normalize_search_text("Hahnemühle Photo Rag®"), "hahnemuhle photo rag")

	def test_words_match_in_any_order(self):
		matches = rank_paper_options(PAPERS, "baryta hahnemuhle")
		self.assertEqual(matches[0]["name"], "HAH-PHOTO-RAG-BARYTA")

	def test_extra_descriptor_does_not_hide_a_strong_match(self):
		matches = rank_paper_options(PAPERS, "Hahnemuhle matte baryta")
		self.assertEqual(matches[0]["name"], "HAH-PHOTO-RAG-BARYTA")

	def test_small_misspelling_still_matches(self):
		matches = rank_paper_options(PAPERS, "Hahnemule baryta")
		self.assertEqual(matches[0]["name"], "HAH-PHOTO-RAG-BARYTA")

	def test_common_dimension_notation_is_equivalent(self):
		self.assertEqual(normalize_search_text("13 × 19 in"), "13x19 in")
		self.assertEqual(normalize_search_text("13 x 19 in"), "13x19 in")


if __name__ == "__main__":
	unittest.main()
