from __future__ import annotations

import math
import re
from dataclasses import dataclass


class DomainError(ValueError):
	pass


@dataclass(frozen=True)
class ReceiptPlan:
	purchase_units: int
	stock_quantity: float
	physical_units: int
	quantity_per_batch: float | None
	stock_rate: float


@dataclass(frozen=True)
class QuantityChange:
	before: float
	change: float
	after: float


_CASE_ROLL_RE = re.compile(r"^Case\s+(\d+)\s*(?:×|x)\s*.+\s+Foot\s+Rolls$", re.IGNORECASE)
_SINGLE_ROLL_RE = re.compile(r"^Roll\s+.+\s+Foot$", re.IGNORECASE)


def _finite_number(name: str, value: object, *, minimum: float | None = None) -> float:
	try:
		number = float(value)
	except (TypeError, ValueError) as exc:
		raise DomainError(f"{name} must be a number.") from exc

	if not math.isfinite(number):
		raise DomainError(f"{name} must be finite.")
	if minimum is not None and number < minimum:
		raise DomainError(f"{name} must be at least {minimum:g}.")
	return number


def physical_units_for_uom(uom: str, *, batched: bool) -> int:
	if not batched:
		return 1

	case_match = _CASE_ROLL_RE.match(uom.strip())
	if case_match:
		return int(case_match.group(1))
	if _SINGLE_ROLL_RE.match(uom.strip()):
		return 1

	raise DomainError("A batched roll must be received with a Roll or Case-of-rolls UOM.")


def plan_receipt(
	*,
	purchase_units: object,
	conversion_factor: object,
	unit_cost: object,
	purchase_uom: str,
	batched: bool,
) -> ReceiptPlan:
	units = _finite_number("Number of packages", purchase_units, minimum=1)
	if not units.is_integer():
		raise DomainError("Number of packages must be a whole number.")

	conversion = _finite_number("UOM conversion factor", conversion_factor, minimum=0.000001)
	cost = _finite_number("Unit cost", unit_cost, minimum=0)
	physical_per_package = physical_units_for_uom(purchase_uom, batched=batched)
	physical_units = int(units) * physical_per_package
	stock_quantity = units * conversion
	quantity_per_batch = stock_quantity / physical_units if batched else None

	return ReceiptPlan(
		purchase_units=int(units),
		stock_quantity=stock_quantity,
		physical_units=physical_units,
		quantity_per_batch=quantity_per_batch,
		stock_rate=cost / conversion,
	)


def calculate_consumption(*, current: object, mode: str, value: object) -> QuantityChange:
	before = _finite_number("Current quantity", current, minimum=0)
	entered = _finite_number("Entered quantity", value, minimum=0)

	if mode == "amount":
		used = entered
	elif mode == "ending":
		if entered > before:
			raise DomainError("Ending balance cannot exceed the current balance.")
		used = before - entered
	else:
		raise DomainError("Consumption mode must be 'amount' or 'ending'.")

	if used <= 0:
		raise DomainError("The consumed quantity must be greater than zero.")
	if used > before:
		raise DomainError("The consumed quantity cannot exceed the current balance.")

	after = before - used
	return QuantityChange(before=before, change=-used, after=after)


def calculate_reconciliation(*, current: object, actual: object) -> QuantityChange:
	before = _finite_number("Current quantity", current, minimum=0)
	after = _finite_number("Actual remaining quantity", actual, minimum=0)
	change = after - before
	if math.isclose(change, 0, abs_tol=1e-9):
		raise DomainError("The measured balance already matches ERPNext.")
	return QuantityChange(before=before, change=change, after=after)
