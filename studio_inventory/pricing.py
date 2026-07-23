from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping, Sequence

from studio_inventory.domain import DomainError


FORMULA_VERSION = "2"


@dataclass(frozen=True)
class PricingRules:
	hourly_rate: float = 75
	ink_cost_per_sq_in: float = 0.012
	production_base: float = 2
	production_first_rate: float = 0.075
	production_large_rate: float = 0.055
	production_breakpoint_sq_in: float = 320
	material_markup: float = 2
	minimum_price_4x6: float = 4
	minimum_price_5x7: float = 6
	minimum_price_8x10: float = 8
	minimum_pricing_margin_pct: float = 0
	unit_price_rounding: float = 1
	low_margin_threshold_pct: float = 35
	roll_consumption_increment_ft: float = 1

	@classmethod
	def from_mapping(cls, values: Mapping[str, object] | None) -> PricingRules:
		if not values:
			return cls()
		defaults = cls()
		parsed = {}
		for name in asdict(defaults):
			value = values.get(name, getattr(defaults, name))
			if value in (None, ""):
				value = getattr(defaults, name)
			parsed[name] = _finite_number(name.replace("_", " ").title(), value, minimum=0)
		if parsed["unit_price_rounding"] <= 0:
			raise DomainError("Unit price rounding must be greater than zero.")
		if parsed["roll_consumption_increment_ft"] <= 0:
			raise DomainError("Roll consumption increment must be greater than zero.")
		if parsed["minimum_pricing_margin_pct"] >= 100:
			raise DomainError("Minimum pricing margin must be less than 100 percent.")
		return cls(**parsed)


@dataclass(frozen=True)
class PriceAdjustment:
	rule_name: str
	priority: int
	target: str
	operation: str
	value: float


@dataclass(frozen=True)
class PaperDimensions:
	stock_uom: str
	width_in: float
	height_in: float | None = None


@dataclass(frozen=True)
class ConsumptionEstimate:
	quantity: float
	uom: str
	orientation: str
	prints_across: int
	prints_per_sheet: int | None = None


@dataclass(frozen=True)
class PrintCalculation:
	formula_version: str
	quantity: int
	printed_area_sq_in: float
	finished_width_in: float
	finished_height_in: float
	material_area_sq_in: float
	production_allowance: float
	minimum_unit_price: float
	margin_floor_unit_price: float
	list_unit_price: float
	line_total: float
	unit_paper_cost: float
	actual_unit_paper_cost: float
	unit_ink_cost: float
	paper_cost: float
	ink_cost: float
	time_cost: float
	total_cost: float
	gross_profit: float
	gross_margin_pct: float


_DIMENSION_RE = re.compile(
	r"(?P<width>\d+(?:\.\d+)?)\s*(?:×|x|X)\s*(?P<height>\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|in|inch|inches|\")?",
	re.IGNORECASE,
)
_WIDTH_RE = re.compile(r"(?P<width>\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|in|inch|inches|\")?", re.IGNORECASE)


def _finite_number(name: str, value: object, *, minimum: float | None = None) -> float:
	try:
		number = float(value)
	except (TypeError, ValueError) as error:
		raise DomainError(f"{name} must be a number.") from error
	if not math.isfinite(number):
		raise DomainError(f"{name} must be finite.")
	if minimum is not None and number < minimum:
		raise DomainError(f"{name} must be at least {minimum:g}.")
	return number


def _to_inches(value: float, unit: str | None) -> float:
	normalized = (unit or "in").lower()
	if normalized == "mm":
		return value / 25.4
	if normalized == "cm":
		return value / 2.54
	return value


def parse_paper_dimensions(*, stock_uom: str, attribute_value: str) -> PaperDimensions:
	text = (attribute_value or "").strip()
	if stock_uom == "Sheet":
		match = _DIMENSION_RE.search(text)
		if not match:
			raise DomainError("The paper Item needs a Sheet Size attribute such as 13 × 19 in.")
		unit = match.group("unit")
		return PaperDimensions(
			stock_uom=stock_uom,
			width_in=_to_inches(float(match.group("width")), unit),
			height_in=_to_inches(float(match.group("height")), unit),
		)
	if stock_uom == "Foot":
		match = _WIDTH_RE.search(text)
		if not match:
			raise DomainError("The paper Item needs a Roll Width attribute such as 24 in width.")
		return PaperDimensions(
			stock_uom=stock_uom,
			width_in=_to_inches(float(match.group("width")), match.group("unit")),
		)
	raise DomainError("Calculated prints currently require a Sheet or Foot stock Item.")


def stock_area_sq_in(dimensions: PaperDimensions) -> float:
	if dimensions.stock_uom == "Sheet" and dimensions.height_in:
		return dimensions.width_in * dimensions.height_in
	if dimensions.stock_uom == "Foot":
		return dimensions.width_in * 12
	raise DomainError("Paper dimensions do not define a usable stock area.")


def cost_per_sq_in(
	*, price: object, conversion_factor: object, dimensions: PaperDimensions
) -> float:
	rate = _finite_number("Item Price", price, minimum=0)
	conversion = _finite_number("UOM conversion factor", conversion_factor, minimum=0.000001)
	return rate / conversion / stock_area_sq_in(dimensions)


def consumed_paper_cost(
	*,
	dimensions: PaperDimensions,
	consumption_quantity: object,
	paper_cost_per_sq_in: object,
) -> float:
	quantity = _finite_number("Paper consumption", consumption_quantity, minimum=0)
	rate = _finite_number("Paper cost per square inch", paper_cost_per_sq_in, minimum=0)
	return quantity * stock_area_sq_in(dimensions) * rate


def _round_to_step(value: float, step: float) -> float:
	decimal_value = Decimal(str(value))
	decimal_step = Decimal(str(step))
	return float((decimal_value / decimal_step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * decimal_step)


def _round_up_to_step(value: float, step: float) -> float:
	return math.ceil((value - 1e-12) / step) * step


def _production_allowance(printed_area: float, rules: PricingRules) -> float:
	first_tier = min(printed_area, rules.production_breakpoint_sq_in)
	large_tier = max(0, printed_area - rules.production_breakpoint_sq_in)
	return (
		rules.production_base
		+ first_tier * rules.production_first_rate
		+ large_tier * rules.production_large_rate
	)


def _minimum_price(width: float, height: float, rules: PricingRules) -> float:
	short_edge, long_edge = sorted((width, height))
	if math.isclose(short_edge, 4) and math.isclose(long_edge, 6):
		return rules.minimum_price_4x6
	if math.isclose(short_edge, 5) and math.isclose(long_edge, 7):
		return rules.minimum_price_5x7
	if math.isclose(short_edge, 8) and math.isclose(long_edge, 10):
		return rules.minimum_price_8x10
	return 0


def _apply_adjustment(current: float, adjustment: PriceAdjustment) -> float:
	if adjustment.operation == "set":
		value = adjustment.value
	elif adjustment.operation == "add":
		value = current + adjustment.value
	elif adjustment.operation == "multiply":
		value = current * adjustment.value
	else:
		raise DomainError(f"Pricing rule {adjustment.rule_name} has an unsupported operation.")
	if value < 0:
		raise DomainError(f"Pricing rule {adjustment.rule_name} produces a negative price.")
	return value


def _adjust_price(
	value: float,
	target: str,
	adjustments: Sequence[PriceAdjustment],
) -> float:
	for adjustment in adjustments:
		if adjustment.target == target:
			value = _apply_adjustment(value, adjustment)
	return value


def calculate_print(
	*,
	artwork_width_in: object,
	artwork_height_in: object,
	border_in: object,
	quantity: object,
	time_minutes: object,
	ink_cost_per_sq_in: object,
	paper_cost_per_sq_in: object,
	rules: PricingRules | None = None,
	price_adjustments: Sequence[PriceAdjustment] = (),
	actual_paper_cost: object | None = None,
) -> PrintCalculation:
	rules = rules or PricingRules()
	width = _finite_number("Artwork width", artwork_width_in, minimum=0.000001)
	height = _finite_number("Artwork height", artwork_height_in, minimum=0.000001)
	border = _finite_number("Border", border_in, minimum=0)
	qty = _finite_number("Quantity", quantity, minimum=1)
	if not qty.is_integer():
		raise DomainError("Quantity must be a whole number.")
	time = _finite_number("Production time", time_minutes, minimum=0)
	ink_rate = _finite_number("Ink cost per square inch", ink_cost_per_sq_in, minimum=0)
	paper_rate = _finite_number("Paper cost per square inch", paper_cost_per_sq_in, minimum=0)

	printed_area = width * height
	finished_width = width + border * 2
	finished_height = height + border * 2
	material_area = finished_width * finished_height
	unit_paper_cost = material_area * paper_rate
	unit_ink_cost = printed_area * ink_rate
	production = _production_allowance(printed_area, rules)
	paper_cost = (
		unit_paper_cost * int(qty)
		if actual_paper_cost is None
		else _finite_number("Actual paper cost", actual_paper_cost, minimum=0)
	)
	actual_unit_paper_cost = paper_cost / int(qty)
	ink_cost = unit_ink_cost * int(qty)
	time_cost = time * rules.hourly_rate / 60
	pricing_unit_cost = unit_paper_cost + unit_ink_cost + time_cost / int(qty)
	margin_floor_price = (
		pricing_unit_cost / (1 - rules.minimum_pricing_margin_pct / 100)
		if rules.minimum_pricing_margin_pct
		else 0
	)
	minimum_price = _adjust_price(
		_minimum_price(width, height, rules),
		"minimum_unit_price",
		price_adjustments,
	)
	raw_price = _adjust_price(
		production + rules.material_markup * (unit_paper_cost + unit_ink_cost),
		"raw_unit_price",
		price_adjustments,
	)
	final_price = _adjust_price(
		max(raw_price, minimum_price, margin_floor_price),
		"final_unit_price",
		price_adjustments,
	)
	unit_price = _round_to_step(final_price, rules.unit_price_rounding)
	if (
		not any(adjustment.target == "final_unit_price" for adjustment in price_adjustments)
		and unit_price < margin_floor_price
	):
		unit_price = _round_up_to_step(margin_floor_price, rules.unit_price_rounding)
	line_total = unit_price * int(qty)
	total_cost = paper_cost + ink_cost + time_cost
	gross_profit = line_total - total_cost
	margin = gross_profit / line_total * 100 if line_total else 0

	return PrintCalculation(
		formula_version=FORMULA_VERSION,
		quantity=int(qty),
		printed_area_sq_in=printed_area,
		finished_width_in=finished_width,
		finished_height_in=finished_height,
		material_area_sq_in=material_area,
		production_allowance=production,
		minimum_unit_price=minimum_price,
		margin_floor_unit_price=margin_floor_price,
		list_unit_price=unit_price,
		line_total=line_total,
		unit_paper_cost=unit_paper_cost,
		actual_unit_paper_cost=actual_unit_paper_cost,
		unit_ink_cost=unit_ink_cost,
		paper_cost=paper_cost,
		ink_cost=ink_cost,
		time_cost=time_cost,
		total_cost=total_cost,
		gross_profit=gross_profit,
		gross_margin_pct=margin,
	)


def estimate_consumption(
	*,
	dimensions: PaperDimensions,
	finished_width_in: object,
	finished_height_in: object,
	quantity: object,
	roll_increment_ft: object = 1,
) -> ConsumptionEstimate:
	width = _finite_number("Finished width", finished_width_in, minimum=0.000001)
	height = _finite_number("Finished height", finished_height_in, minimum=0.000001)
	qty = _finite_number("Quantity", quantity, minimum=1)
	if not qty.is_integer():
		raise DomainError("Quantity must be a whole number.")

	if dimensions.stock_uom == "Sheet" and dimensions.height_in:
		layouts = []
		for orientation, across_size, along_size in (
			("width-across", width, height),
			("height-across", height, width),
		):
			across = math.floor(dimensions.width_in / across_size)
			along = math.floor(dimensions.height_in / along_size)
			yield_per_sheet = across * along
			if yield_per_sheet:
				layouts.append((yield_per_sheet, orientation, across))
		if not layouts:
			raise DomainError(
				f'The {width:g} × {height:g} in finished print does not fit the '
				f'{dimensions.width_in:g} × {dimensions.height_in:g} in sheet.'
			)
		prints_per_sheet, orientation, across = max(layouts, key=lambda value: (value[0], value[2]))
		sheets = math.ceil(int(qty) / prints_per_sheet)
		return ConsumptionEstimate(
			quantity=sheets,
			uom="Sheet",
			orientation=orientation,
			prints_across=across,
			prints_per_sheet=prints_per_sheet,
		)

	if dimensions.stock_uom == "Foot":
		increment = _finite_number("Roll consumption increment", roll_increment_ft, minimum=0.000001)
		layouts = []
		for orientation, across_size, along_size in (
			("width-across", width, height),
			("height-across", height, width),
		):
			across = math.floor(dimensions.width_in / across_size)
			if not across:
				continue
			rows = math.ceil(int(qty) / across)
			length_ft = rows * along_size / 12
			layouts.append((length_ft, orientation, across))
		if not layouts:
			raise DomainError(
				f'The {width:g} × {height:g} in finished print is wider than the '
				f'{dimensions.width_in:g} in roll in both orientations.'
			)
		length_ft, orientation, across = min(layouts, key=lambda value: (value[0], -value[2]))
		rounded_length = math.ceil((length_ft - 1e-12) / increment) * increment
		return ConsumptionEstimate(
			quantity=rounded_length,
			uom="Foot",
			orientation=orientation,
			prints_across=across,
		)

	raise DomainError("Calculated prints currently require a Sheet or Foot stock Item.")
