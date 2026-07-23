from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from studio_inventory.domain import DomainError
from studio_inventory.pricing import PriceAdjustment, PricingRules


TARGET_KEYS = {
	"Internal Hourly Cost": "hourly_rate",
	"Ink Cost per Square Inch": "ink_cost_per_sq_in",
	"Material Markup Multiplier": "material_markup",
	"Unit Price Rounding": "unit_price_rounding",
	"Production Base Allowance": "production_base",
	"First-Tier Rate per Square Inch": "production_first_rate",
	"Large-Print Rate per Square Inch": "production_large_rate",
	"Large-Print Breakpoint": "production_breakpoint_sq_in",
	"Minimum 4 × 6 Price": "minimum_price_4x6",
	"Minimum 5 × 7 Price": "minimum_price_5x7",
	"Minimum 8 × 10 Price": "minimum_price_8x10",
	"Minimum Pricing Margin": "minimum_pricing_margin_pct",
	"Low-Margin Warning Threshold": "low_margin_threshold_pct",
	"Roll Consumption Increment": "roll_consumption_increment_ft",
	"Minimum Unit Price": "minimum_unit_price",
	"Raw Unit Price": "raw_unit_price",
	"Final Unit Price": "final_unit_price",
}
PRICE_TARGETS = {"minimum_unit_price", "raw_unit_price", "final_unit_price"}
OPERATIONS = {"Set": "set", "Add": "add", "Multiply": "multiply"}


@dataclass(frozen=True)
class PricingRuleContext:
	paper_item: str
	paper_brand: str | None
	stock_uom: str
	artwork_width_in: float
	artwork_height_in: float
	paper_cost_per_sq_in: float
	quantity: int


@dataclass(frozen=True)
class PricingResolution:
	rules: PricingRules
	price_adjustments: tuple[PriceAdjustment, ...]
	matched_rules: tuple[dict[str, object], ...]


def _get(row: object, fieldname: str, default=None):
	if isinstance(row, Mapping):
		return row.get(fieldname, default)
	getter = getattr(row, "get", None)
	if getter:
		value = getter(fieldname)
		return default if value is None else value
	return getattr(row, fieldname, default)


def _present(value: object) -> bool:
	return value not in (None, "")


def _number(label: str, value: object) -> float:
	try:
		number = float(value)
	except (TypeError, ValueError) as error:
		raise DomainError(f"{label} must be a number.") from error
	if not math.isfinite(number):
		raise DomainError(f"{label} must be finite.")
	return number


def _enabled(row: object) -> bool:
	value = _get(row, "enabled", 1)
	return value not in (0, "0", False)


def _target_key(row: object) -> str:
	target = str(_get(row, "target") or "")
	if target in TARGET_KEYS:
		return TARGET_KEYS[target]
	if target in set(TARGET_KEYS.values()):
		return target
	raise DomainError(f"Pricing rule {_rule_name(row)} has an unsupported target.")


def _operation(row: object) -> str:
	operation = str(_get(row, "operation") or "")
	if operation in OPERATIONS:
		return OPERATIONS[operation]
	if operation.lower() in OPERATIONS.values():
		return operation.lower()
	raise DomainError(f"Pricing rule {_rule_name(row)} has an unsupported operation.")


def _rule_name(row: object) -> str:
	return str(_get(row, "rule_name") or "Unnamed pricing rule")


def _priority(row: object) -> int:
	value = _get(row, "priority", 100)
	number = _number(f"Priority for {_rule_name(row)}", 100 if value in (None, "") else value)
	if not number.is_integer():
		raise DomainError(f"Priority for {_rule_name(row)} must be a whole number.")
	return int(number)


def _validate_bounds(row: object, minimum_field: str, maximum_field: str, label: str) -> None:
	minimum_value = _get(row, minimum_field)
	maximum_value = _get(row, maximum_field)
	if _present(minimum_value) and _number(f"Minimum {label}", minimum_value) < 0:
		raise DomainError(f"Minimum {label} cannot be negative.")
	if _present(maximum_value) and _number(f"Maximum {label}", maximum_value) < 0:
		raise DomainError(f"Maximum {label} cannot be negative.")
	if (
		_present(minimum_value)
		and _present(maximum_value)
		and _number(f"Minimum {label}", minimum_value)
		> _number(f"Maximum {label}", maximum_value)
	):
		raise DomainError(f"Minimum {label} cannot exceed maximum {label}.")


def validate_rule_definitions(rows: Iterable[object]) -> None:
	for row in rows:
		width = _get(row, "exact_width_in")
		height = _get(row, "exact_height_in")
		if _present(width) != _present(height):
			raise DomainError(f"Pricing rule {_rule_name(row)} needs both width and height for an exact size.")
		if _present(width) and (
			_number("Exact artwork width", width) <= 0
			or _number("Exact artwork height", height) <= 0
		):
			raise DomainError(f"Pricing rule {_rule_name(row)} exact dimensions must be greater than zero.")

		_validate_bounds(row, "min_artwork_area_sq_in", "max_artwork_area_sq_in", "artwork area")
		_validate_bounds(
			row,
			"min_paper_cost_per_sq_in",
			"max_paper_cost_per_sq_in",
			"paper cost",
		)
		_validate_bounds(row, "min_quantity", "max_quantity", "quantity")

		target = _target_key(row)
		operation = _operation(row)
		value = _number(f"Value for {_rule_name(row)}", _get(row, "value"))
		if operation == "multiply" and value < 0:
			raise DomainError(f"Pricing rule {_rule_name(row)} cannot use a negative multiplier.")
		_priority(row)


def _matches(row: object, context: PricingRuleContext) -> bool:
	if not _enabled(row):
		return False
	for fieldname, actual in (
		("paper_item", context.paper_item),
		("paper_brand", context.paper_brand),
		("stock_uom", context.stock_uom),
	):
		expected = _get(row, fieldname)
		if _present(expected) and str(expected) != str(actual or ""):
			return False

	width = _get(row, "exact_width_in")
	height = _get(row, "exact_height_in")
	if _present(width):
		expected_edges = sorted((_number("Exact artwork width", width), _number("Exact artwork height", height)))
		actual_edges = sorted((context.artwork_width_in, context.artwork_height_in))
		if not all(
			math.isclose(expected, actual, abs_tol=1e-6)
			for expected, actual in zip(expected_edges, actual_edges)
		):
			return False

	area = context.artwork_width_in * context.artwork_height_in
	for minimum_field, maximum_field, actual in (
		("min_artwork_area_sq_in", "max_artwork_area_sq_in", area),
		(
			"min_paper_cost_per_sq_in",
			"max_paper_cost_per_sq_in",
			context.paper_cost_per_sq_in,
		),
		("min_quantity", "max_quantity", context.quantity),
	):
		minimum_value = _get(row, minimum_field)
		maximum_value = _get(row, maximum_field)
		if _present(minimum_value) and actual < _number(minimum_field, minimum_value):
			return False
		if _present(maximum_value) and actual > _number(maximum_field, maximum_value):
			return False
	return True


def _apply(current: float, operation: str, value: float, rule_name: str) -> float:
	if operation == "set":
		result = value
	elif operation == "add":
		result = current + value
	else:
		result = current * value
	if result < 0:
		raise DomainError(f"Pricing rule {rule_name} produces a negative model value.")
	return result


def resolve_pricing_model(
	base_rules: PricingRules,
	rule_rows: Iterable[object],
	context: PricingRuleContext,
) -> PricingResolution:
	rows = list(rule_rows)
	validate_rule_definitions(rows)
	values = asdict(base_rules)
	price_adjustments = []
	matched_rules = []
	matched_priority_targets = set()
	for row in sorted(rows, key=lambda candidate: (_priority(candidate), int(_get(candidate, "idx", 0) or 0))):
		if not _matches(row, context):
			continue
		name = _rule_name(row)
		target = _target_key(row)
		operation = _operation(row)
		value = _number(f"Value for {name}", _get(row, "value"))
		priority = _priority(row)
		priority_target = (priority, target)
		if priority_target in matched_priority_targets:
			raise DomainError(
				"Multiple pricing rules with the same priority and target matched this calculation; "
				"give the conflicting rules an explicit order."
			)
		matched_priority_targets.add(priority_target)
		if target in PRICE_TARGETS:
			price_adjustments.append(
				PriceAdjustment(
					rule_name=name,
					priority=priority,
					target=target,
					operation=operation,
					value=value,
				)
			)
		else:
			values[target] = _apply(values[target], operation, value, name)
		matched_rules.append(
			{
				"rule_name": name,
				"priority": priority,
				"target": target,
				"operation": operation,
				"value": value,
			}
		)
	return PricingResolution(
		rules=PricingRules.from_mapping(values),
		price_adjustments=tuple(price_adjustments),
		matched_rules=tuple(matched_rules),
	)
