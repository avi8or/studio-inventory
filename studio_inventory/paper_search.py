from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any


_CHARACTER_ALIASES = str.maketrans({"œ": "oe", "æ": "ae", "ø": "o", "ß": "ss", "×": " x "})
_TRADEMARK_SYMBOLS = str.maketrans({"®": " ", "™": " ", "℠": " "})


def normalize_search_text(value: object) -> str:
	text = unicodedata.normalize("NFKD", str(value or "").casefold()).translate(_CHARACTER_ALIASES)
	text = "".join(character for character in text if not unicodedata.combining(character))
	text = text.translate(_TRADEMARK_SYMBOLS)
	text = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "x", text)
	return " ".join(re.findall(r"[a-z0-9]+", text))


def _tokens(value: object) -> tuple[str, ...]:
	return tuple(normalize_search_text(value).split())


def _edit_distance(left: str, right: str) -> int:
	previous = list(range(len(right) + 1))
	for left_index, left_character in enumerate(left, start=1):
		current = [left_index]
		for right_index, right_character in enumerate(right, start=1):
			current.append(
				min(
					current[right_index - 1] + 1,
					previous[right_index] + 1,
					previous[right_index - 1] + (left_character != right_character),
				)
			)
		previous = current
	return previous[-1]


def _token_match_score(query_token: str, candidate_token: str) -> int:
	if query_token == candidate_token:
		return 100
	if len(query_token) >= 2 and candidate_token.startswith(query_token):
		return 80
	if len(query_token) >= 3 and query_token in candidate_token:
		return 70
	allowed_distance = 2 if len(query_token) >= 7 else 1 if len(query_token) >= 4 else 0
	if not allowed_distance or abs(len(query_token) - len(candidate_token)) > allowed_distance:
		return 0
	distance = _edit_distance(query_token, candidate_token)
	return 60 - distance * 5 if distance <= allowed_distance else 0


def _field_token_score(query_token: str, value: object, weight: int) -> int:
	best = max((_token_match_score(query_token, token) for token in _tokens(value)), default=0)
	return best + weight if best else 0


def _option_score(option: Mapping[str, Any], query: str) -> int | None:
	query_tokens = _tokens(query)
	if not query_tokens:
		return 0
	fields = (
		(option.get("item_name"), 30),
		(option.get("brand"), 25),
		(option.get("name"), 20),
		(option.get("stock_uom"), 5),
	)
	matched = 0
	score = 0
	for query_token in query_tokens:
		token_score = max(_field_token_score(query_token, value, weight) for value, weight in fields)
		if not token_score:
			continue
		matched += 1
		score += token_score
	if matched < math.ceil(len(query_tokens) / 2):
		return None

	normalized_name = normalize_search_text(option.get("item_name"))
	normalized_code = normalize_search_text(option.get("name"))
	score += matched * 1000 - (len(query_tokens) - matched) * 150
	if matched == len(query_tokens):
		score += 300
	if normalized_name.startswith(query):
		score += 200
	elif query in normalized_name:
		score += 100
	if normalized_code == query:
		score += 300
	return score


def rank_paper_options(options: Sequence[Mapping[str, Any]], query: object) -> list[Mapping[str, Any]]:
	normalized_query = normalize_search_text(query)
	if not normalized_query:
		return list(options)
	matches = []
	for option in options:
		score = _option_score(option, normalized_query)
		if score is not None:
			matches.append(
				(
					score,
					normalize_search_text(option.get("item_name")),
					str(option.get("name") or ""),
					option,
				)
			)
	matches.sort(key=lambda match: (-match[0], match[1], match[2]))
	return [match[3] for match in matches]
