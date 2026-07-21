from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import cint, flt, get_url_to_list, getdate, nowdate

from studio_inventory.domain import DomainError
from studio_inventory.permissions import has_pricing_access
from studio_inventory.pricing import (
	FORMULA_VERSION,
	PaperDimensions,
	PricingRules,
	calculate_print as calculate_print_price,
	cost_per_sq_in,
	estimate_consumption,
	parse_paper_dimensions,
)


PRICING_MANAGER_ROLES = {"Sales Manager", "System Manager"}
PAPER_ATTRIBUTE_BY_UOM = {"Sheet": "Sheet Size", "Foot": "Roll Width"}


def _throw_domain(error: DomainError) -> None:
	frappe.throw(_(str(error)), frappe.ValidationError)


def _payload(value: dict | str) -> dict[str, Any]:
	if isinstance(value, dict):
		return value
	try:
		parsed = json.loads(value)
	except (TypeError, ValueError) as error:
		frappe.throw(_("The calculation payload is not valid JSON."), frappe.ValidationError)
		raise error
	if not isinstance(parsed, dict):
		frappe.throw(_("The calculation payload must be an object."), frappe.ValidationError)
	return parsed


def _pricing_settings():
	return frappe.get_cached_doc("Studio Pricing Settings")


def _company(settings=None) -> str | None:
	settings = settings or _pricing_settings()
	return (
		settings.company
		or frappe.defaults.get_user_default("Company")
		or frappe.defaults.get_global_default("company")
	)


def _paper_cost_price_list(settings=None) -> str:
	settings = settings or _pricing_settings()
	return settings.paper_cost_price_list or "Standard Buying"


def _rules(settings=None) -> PricingRules:
	settings = settings or _pricing_settings()
	return PricingRules.from_mapping(
		{
			name: settings.get(name)
			for name in PricingRules.__dataclass_fields__
		}
	)


def _paper_item(item_code: str):
	if not item_code:
		frappe.throw(_("Paper Item is required."), frappe.ValidationError)
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	if item.disabled or not item.is_stock_item or item.has_variants:
		frappe.throw(_("Choose an active stock Item variant for the paper."), frappe.ValidationError)
	if item.stock_uom not in PAPER_ATTRIBUTE_BY_UOM:
		frappe.throw(_("Calculated prints currently require a Sheet or Foot stock Item."), frappe.ValidationError)
	return item


def _print_item(item_code: str):
	if not item_code:
		frappe.throw(_("Print Item is required."), frappe.ValidationError)
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	if item.disabled or not item.is_sales_item or item.has_variants:
		frappe.throw(
			_("Choose an active, sellable Item without variants for the quotation line."),
			frappe.ValidationError,
		)
	return item


def _item_dimensions(item) -> PaperDimensions:
	attribute_name = PAPER_ATTRIBUTE_BY_UOM[item.stock_uom]
	attribute_value = next(
		(row.attribute_value for row in item.attributes if row.attribute == attribute_name),
		None,
	)
	if not attribute_value:
		raise DomainError(f"Item {item.name} needs the {attribute_name} variant attribute.")
	return parse_paper_dimensions(stock_uom=item.stock_uom, attribute_value=attribute_value)


def _conversion_factor(item, uom: str | None) -> float:
	if not uom or uom == item.stock_uom:
		return 1
	for row in item.uoms:
		if row.uom == uom:
			return flt(row.conversion_factor)
	raise DomainError(f"UOM {uom} is not configured on Item {item.name}.")


def _cost_basis(item, settings=None) -> dict[str, Any] | None:
	settings = settings or _pricing_settings()
	dimensions = _item_dimensions(item)
	fields = [
		"name",
		"price_list",
		"price_list_rate",
		"uom",
		"supplier",
		"valid_from",
		"valid_upto",
		"note",
	]
	if frappe.db.has_column("Item Price", "si_merchant_url"):
		fields.extend(["si_merchant_url", "si_last_verified_on"])
	rows = frappe.get_list(
		"Item Price",
		filters={
			"item_code": item.name,
			"price_list": _paper_cost_price_list(settings),
		},
		fields=fields,
		order_by="valid_from desc, modified desc",
		limit_page_length=100,
	)
	today = getdate(nowdate())
	candidates = []
	for row in rows:
		if row.valid_from and getdate(row.valid_from) > today:
			continue
		if row.valid_upto and getdate(row.valid_upto) < today:
			continue
		try:
			conversion = _conversion_factor(item, row.uom)
			cost = cost_per_sq_in(
				price=row.price_list_rate,
				conversion_factor=conversion,
				dimensions=dimensions,
			)
		except DomainError:
			continue
		candidates.append((cost, row, conversion))
	if not candidates:
		return None
	cost, row, conversion = max(
		candidates,
		key=lambda candidate: (candidate[0], flt(candidate[1].price_list_rate)),
	)
	return {
		"cost_per_sq_in": cost,
		"item_price": row.name,
		"price_list": row.price_list,
		"rate": flt(row.price_list_rate),
		"uom": row.uom or item.stock_uom,
		"conversion_factor": conversion,
		"supplier": row.supplier,
		"merchant_url": row.get("si_merchant_url"),
		"last_verified_on": (
			str(row.get("si_last_verified_on")) if row.get("si_last_verified_on") else None
		),
		"note": row.note,
	}


def _can_override_cost() -> bool:
	return bool(PRICING_MANAGER_ROLES.intersection(frappe.get_roles()))


def _check_pricing_permission() -> None:
	if has_pricing_access():
		return
	frappe.throw(_("You do not have permission to use print pricing."), frappe.PermissionError)


def _paper_options() -> list[dict[str, Any]]:
	return frappe.get_list(
		"Item",
		filters={
			"disabled": 0,
			"is_stock_item": 1,
			"has_variants": 0,
			"stock_uom": ["in", list(PAPER_ATTRIBUTE_BY_UOM)],
		},
		fields=["name", "item_name", "stock_uom", "brand"],
		order_by="item_name asc",
		limit_page_length=0,
	)


def _calculation_payload(data: dict[str, Any], *, settings=None) -> dict[str, Any]:
	settings = settings or _pricing_settings()
	rules = _rules(settings)
	print_item = _print_item(str(data.get("print_item") or settings.default_print_item or ""))
	paper_item = _paper_item(str(data.get("paper_item") or ""))
	dimensions = _item_dimensions(paper_item)
	cost_override = data.get("cost_override")
	if cost_override in (None, ""):
		basis = _cost_basis(paper_item, settings)
		if not basis:
			frappe.throw(
				_(
					"No current Item Price exists for {0} in {1}. "
					"Add one or ask a Pricing Manager to enter a cost override."
				).format(
					frappe.bold(paper_item.name), frappe.bold(_paper_cost_price_list(settings))
				),
				frappe.ValidationError,
			)
		paper_cost = basis["cost_per_sq_in"]
		cost_source = basis
		cost_was_overridden = False
	else:
		if not _can_override_cost():
			frappe.throw(_("Only a Sales Manager or System Manager can override paper cost."), frappe.PermissionError)
		try:
			paper_cost = float(cost_override)
		except (TypeError, ValueError) as error:
			raise DomainError("Paper cost override must be a number.") from error
		cost_source = {"cost_per_sq_in": paper_cost, "override": True}
		cost_was_overridden = True

	ink_cost = data.get("ink_cost_per_sq_in")
	if ink_cost in (None, ""):
		ink_cost = rules.ink_cost_per_sq_in
	calculation = calculate_print_price(
		artwork_width_in=data.get("artwork_width_in"),
		artwork_height_in=data.get("artwork_height_in"),
		border_in=data.get("border_in", 0),
		quantity=data.get("quantity", 1),
		time_minutes=data.get("time_minutes", 0),
		ink_cost_per_sq_in=ink_cost,
		paper_cost_per_sq_in=paper_cost,
		rules=rules,
	)
	consumption = estimate_consumption(
		dimensions=dimensions,
		finished_width_in=calculation.finished_width_in,
		finished_height_in=calculation.finished_height_in,
		quantity=calculation.quantity,
		roll_increment_ft=rules.roll_consumption_increment_ft,
	)
	warnings = []
	if calculation.gross_margin_pct < rules.low_margin_threshold_pct:
		warnings.append(
			_("Gross margin {0:.1f}% is below the {1:.1f}% warning threshold.").format(
				calculation.gross_margin_pct, rules.low_margin_threshold_pct
			)
		)

	description = _("{0}<br>Paper: {1}<br>Artwork: {2:g} × {3:g} in; finished: {4:g} × {5:g} in").format(
		print_item.item_name,
		paper_item.item_name,
		flt(data.get("artwork_width_in")),
		flt(data.get("artwork_height_in")),
		calculation.finished_width_in,
		calculation.finished_height_in,
	)
	snapshot = {
		"formula_version": FORMULA_VERSION,
		"inputs": {
			"print_item": print_item.name,
			"paper_item": paper_item.name,
			"artwork_width_in": flt(data.get("artwork_width_in")),
			"artwork_height_in": flt(data.get("artwork_height_in")),
			"border_in": flt(data.get("border_in")),
			"quantity": calculation.quantity,
			"time_minutes": flt(data.get("time_minutes")),
			"ink_cost_per_sq_in": flt(ink_cost),
			"paper_cost_per_sq_in": paper_cost,
		},
		"rules": asdict(rules),
		"cost_source": cost_source,
		"calculation": asdict(calculation),
		"consumption": asdict(consumption),
	}
	return {
		"print_item": {"item_code": print_item.name, "item_name": print_item.item_name},
		"paper_item": {
			"item_code": paper_item.name,
			"item_name": paper_item.item_name,
			"stock_uom": paper_item.stock_uom,
			"dimensions": asdict(dimensions),
		},
		"paper_cost_per_sq_in": paper_cost,
		"cost_source": cost_source,
		"cost_was_overridden": cost_was_overridden,
		"calculation": asdict(calculation),
		"consumption": asdict(consumption),
		"description": description,
		"warnings": warnings,
		"snapshot": json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
	}


@frappe.whitelist(methods=["POST"])
def get_pricing_context(include_paper_items: bool = False) -> dict:
	_check_pricing_permission()
	settings = _pricing_settings()
	rules = _rules(settings)
	company = _company(settings)
	context = {
		"company": company,
		"currency": frappe.db.get_value("Company", company, "default_currency") if company else None,
		"default_print_item": settings.default_print_item,
		"paper_cost_price_list": _paper_cost_price_list(settings),
		"ink_cost_per_sq_in": rules.ink_cost_per_sq_in,
		"low_margin_threshold_pct": rules.low_margin_threshold_pct,
		"can_override_cost": _can_override_cost(),
	}
	if cint(include_paper_items):
		context["paper_items"] = _paper_options()
	return context


@frappe.whitelist(methods=["POST"])
def get_paper_cost(item_code: str) -> dict:
	_check_pricing_permission()
	item = _paper_item(item_code)
	try:
		dimensions = _item_dimensions(item)
		basis = _cost_basis(item)
	except DomainError as error:
		_throw_domain(error)
		raise
	return {
		"item_code": item.name,
		"item_name": item.item_name,
		"stock_uom": item.stock_uom,
		"dimensions": asdict(dimensions),
		"basis": basis,
	}


@frappe.whitelist(methods=["POST"])
def calculate_print(payload: dict | str) -> dict:
	_check_pricing_permission()
	try:
		return _calculation_payload(_payload(payload))
	except DomainError as error:
		_throw_domain(error)
		raise


def validate_quotation(doc, method: str | None = None) -> None:
	settings = _pricing_settings()
	rules = _rules(settings)
	changed = False
	for row in doc.items:
		if not row.get("si_is_calculated_print"):
			continue
		try:
			paper_item = _paper_item(row.si_paper_item)
			dimensions = _item_dimensions(paper_item)
			calculation = calculate_print_price(
				artwork_width_in=row.si_artwork_width_in,
				artwork_height_in=row.si_artwork_height_in,
				border_in=row.si_border_in,
				quantity=row.qty,
				time_minutes=row.si_time_minutes,
				ink_cost_per_sq_in=row.si_ink_cost_per_sq_in,
				paper_cost_per_sq_in=row.si_paper_cost_per_sq_in,
				rules=rules,
			)
			consumption = estimate_consumption(
				dimensions=dimensions,
				finished_width_in=calculation.finished_width_in,
				finished_height_in=calculation.finished_height_in,
				quantity=calculation.quantity,
				roll_increment_ft=rules.roll_consumption_increment_ft,
			)
		except DomainError as error:
			_throw_domain(error)
			raise

		list_rate = calculation.list_unit_price
		discount_percentage = max(0, min(100, flt(row.discount_percentage)))
		discount_amount = max(0, flt(row.discount_amount))
		if discount_percentage:
			net_rate = list_rate * (1 - discount_percentage / 100)
		elif discount_amount:
			net_rate = max(0, list_rate - discount_amount)
		else:
			net_rate = list_rate
		revenue = net_rate * calculation.quantity
		margin = (revenue - calculation.total_cost) / revenue * 100 if revenue else 0

		row.price_list_rate = list_rate
		row.rate = net_rate
		row.amount = revenue
		row.si_estimated_stock_qty = consumption.quantity
		row.si_estimated_stock_uom = consumption.uom
		row.si_internal_cost = calculation.total_cost
		row.si_gross_margin_pct = margin
		row.si_formula_version = FORMULA_VERSION
		row.si_calculation_snapshot = json.dumps(
			{
				"formula_version": FORMULA_VERSION,
				"rules": asdict(rules),
				"calculation": asdict(calculation),
				"consumption": asdict(consumption),
				"net_unit_rate": net_rate,
				"gross_margin_after_line_discount_pct": margin,
			},
			sort_keys=True,
			separators=(",", ":"),
		)
		changed = True
	if changed:
		doc.calculate_taxes_and_totals()


@frappe.whitelist(methods=["POST"])
def get_quotation_url(crm_deal: str) -> str:
	if not frappe.db.exists("DocType", "CRM Deal"):
		frappe.throw(_("Frappe CRM is not installed on this site."), frappe.ValidationError)
	deal = frappe.get_doc("CRM Deal", crm_deal)
	deal.check_permission("read")
	settings = _pricing_settings()
	contact = next((row.contact for row in deal.contacts if row.is_primary), None)
	address = (
		frappe.db.get_value("CRM Organization", deal.organization, "address")
		if deal.organization
		else None
	)
	params = {
		"quotation_to": "CRM Deal",
		"crm_deal": deal.name,
		"party_name": deal.name,
		"company": _company(settings),
		"contact_person": contact,
		"customer_address": address,
	}
	query = urlencode({key: value for key, value in params.items() if value})
	return f"{get_url_to_list('Quotation')}/new?{query}"
