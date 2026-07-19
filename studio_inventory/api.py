from __future__ import annotations

import json
import re
from typing import Any

import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import flt, now_datetime, nowdate, nowtime

from studio_inventory.domain import (
	DomainError,
	calculate_consumption,
	calculate_reconciliation,
	physical_units_for_uom,
	plan_receipt,
)

APP_MARKER = "[Studio Inventory]"
BATCH_NAMING_SERIES = "SIB.######"
INTERNAL_BARCODE_NAMING_SERIES = "INV######"
INTERNAL_BARCODE_PATTERN = re.compile(r"^INV\d{6}$")
TRANSACTION_DOCTYPES = ("Purchase Receipt", "Stock Entry", "Stock Reconciliation")
VALID_ACTIONS = ("receive", "consume", "count")


def _throw_domain(error: DomainError) -> None:
	frappe.throw(_(str(error)), frappe.ValidationError)


def _payload(value: dict | str) -> dict[str, Any]:
	if isinstance(value, dict):
		return value
	try:
		parsed = json.loads(value)
	except (TypeError, ValueError) as error:
		frappe.throw(_("The request payload is not valid JSON."), frappe.ValidationError)
		raise error
	if not isinstance(parsed, dict):
		frappe.throw(_("The request payload must be an object."), frappe.ValidationError)
	return parsed


def _warehouse_company(warehouse: str) -> str:
	row = frappe.db.get_value(
		"Warehouse",
		warehouse,
		["name", "company", "is_group", "disabled"],
		as_dict=True,
	)
	if not row or row.is_group or row.disabled:
		frappe.throw(_("Choose an active, non-group Warehouse."), frappe.ValidationError)
	frappe.get_doc("Warehouse", warehouse).check_permission("read")
	return row.company


def _item(item_code: str):
	if not item_code:
		frappe.throw(_("Item is required."), frappe.ValidationError)
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	if item.disabled or not item.is_stock_item or item.has_variants:
		frappe.throw(_("Choose an active stock Item variant."), frappe.ValidationError)
	return item


def _batch(batch_no: str, item_code: str | None = None):
	if not batch_no:
		return None
	batch = frappe.get_doc("Batch", batch_no)
	batch.check_permission("read")
	if batch.disabled:
		frappe.throw(_("Batch {0} is disabled.").format(batch_no), frappe.ValidationError)
	if item_code and batch.item != item_code:
		frappe.throw(_("Batch {0} does not belong to Item {1}.").format(batch_no, item_code), frappe.ValidationError)
	return batch


def _conversion_factor(item, uom: str) -> float:
	if uom == item.stock_uom:
		return 1.0
	for row in item.uoms:
		if row.uom == uom:
			return flt(row.conversion_factor)
	frappe.throw(_("UOM {0} is not configured on Item {1}.").format(uom, item.name), frappe.ValidationError)
	return 0.0


def _balance(item_code: str, warehouse: str, batch_no: str | None = None) -> float:
	if batch_no:
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		return flt(get_batch_qty(batch_no=batch_no, warehouse=warehouse, item_code=item_code))

	from erpnext.stock.utils import get_stock_balance

	return flt(get_stock_balance(item_code, warehouse))


def _mark_transaction(doc, action: str, detail: str = "") -> None:
	text = f"{APP_MARKER} {action}"
	if detail:
		text += f": {detail}"
	doc.add_comment("Comment", text=text)


def _next_batch_name() -> str:
	for _attempt in range(100):
		name = make_autoname(BATCH_NAMING_SERIES)
		if not frappe.db.exists("Batch", name):
			return name
	frappe.throw(_("Could not allocate a unique Studio Inventory Batch number."))
	return ""


def _result(doc, *, item, warehouse: str, batch_no: str | None, before: float, change: float, labels=None):
	return {
		"voucher_type": doc.doctype,
		"voucher_no": doc.name,
		"item_code": item.name,
		"item_name": item.item_name,
		"warehouse": warehouse,
		"stock_uom": item.stock_uom,
		"batch_no": batch_no,
		"before": before,
		"change": change,
		"after": _balance(item.name, warehouse, batch_no),
		"labels": labels or [],
		"can_undo": True,
	}


def _select_default_warehouse(warehouses, default_company: str | None, user_default: str | None) -> str | None:
	company_warehouses = [
		warehouse for warehouse in warehouses if not default_company or warehouse.company == default_company
	]
	for warehouse in company_warehouses:
		if (warehouse.warehouse_name or "").strip().casefold() == "stores":
			return warehouse.name
	if user_default and any(warehouse.name == user_default for warehouse in company_warehouses):
		return user_default
	return company_warehouses[0].name if company_warehouses else None


@frappe.whitelist(methods=["POST"])
def get_options() -> dict:
	warehouses = frappe.get_list(
		"Warehouse",
		filters={"is_group": 0, "disabled": 0},
		fields=["name", "warehouse_name", "company"],
		order_by="name asc",
		limit_page_length=500,
	)
	suppliers = frappe.get_list(
		"Supplier",
		filters={"disabled": 0},
		fields=["name", "supplier_name"],
		order_by="supplier_name asc",
		limit_page_length=250,
	)
	default_company = frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default("company")
	default_warehouse = _select_default_warehouse(
		warehouses,
		default_company,
		frappe.defaults.get_user_default("Warehouse"),
	)

	return {
		"warehouses": warehouses,
		"suppliers": suppliers,
		"default_company": default_company,
		"default_warehouse": default_warehouse,
		"default_supplier": frappe.defaults.get_user_default("Supplier"),
		"permissions": {
			"receive": frappe.has_permission("Purchase Receipt", ptype="create")
			and frappe.has_permission("Purchase Receipt", ptype="submit"),
			"consume": frappe.has_permission("Stock Entry", ptype="create")
			and frappe.has_permission("Stock Entry", ptype="submit"),
			"count": frappe.has_permission("Stock Reconciliation", ptype="create")
			and frappe.has_permission("Stock Reconciliation", ptype="submit"),
			"manage_labels": frappe.has_permission("Item", ptype="write"),
		},
	}


@frappe.whitelist(methods=["POST"])
def resolve_scan(code: str, action: str, warehouse: str | None = None) -> dict:
	action = action.strip().lower()
	if action not in VALID_ACTIONS:
		frappe.throw(_("Unknown inventory action."), frappe.ValidationError)

	raw_code = (code or "").strip()
	if not raw_code:
		frappe.throw(_("Scan a barcode or enter an Item code."), frappe.ValidationError)

	warehouse = warehouse or frappe.defaults.get_user_default("Warehouse")
	if not warehouse:
		frappe.throw(_("Choose a Warehouse before scanning."), frappe.ValidationError)
	_warehouse_company(warehouse)

	batch = None
	item_code = None
	barcode_uom = None
	for candidate in dict.fromkeys((raw_code, raw_code.upper())):
		batch_name = frappe.db.get_value("Batch", candidate, "name")
		if batch_name:
			batch = _batch(batch_name)
			item_code = batch.item
			break

		barcode = frappe.db.get_value(
			"Item Barcode",
			{"barcode": candidate},
			["parent", "uom"],
			as_dict=True,
		)
		if barcode:
			item_code = barcode.parent
			barcode_uom = barcode.uom
			break

		if frappe.db.exists("Item", candidate):
			item_code = candidate
			break

	if not item_code:
		frappe.throw(_("No Item or Batch matches {0}.").format(frappe.bold(raw_code)), frappe.DoesNotExistError)

	item = _item(item_code)
	if action == "receive" and batch:
		frappe.throw(_("Scan the Item or manufacturer barcode to receive new stock, not an existing Batch label."))
	if action in ("consume", "count") and item.has_batch_no and not batch:
		frappe.throw(_("This Item is tracked by physical roll. Scan the unique Batch label on the roll."))

	purchase_uoms = []
	seen_uoms = set()
	if not item.has_batch_no:
		purchase_uoms.append({"uom": item.stock_uom, "conversion_factor": 1, "physical_units": 1})
		seen_uoms.add(item.stock_uom)
	for row in item.uoms:
		if row.uom in seen_uoms:
			continue
		try:
			physical_units = physical_units_for_uom(row.uom, batched=bool(item.has_batch_no))
		except DomainError:
			continue
		seen_uoms.add(row.uom)
		purchase_uoms.append(
			{
				"uom": row.uom,
				"conversion_factor": flt(row.conversion_factor),
				"physical_units": physical_units,
			}
		)

	return {
		"scan_code": raw_code,
		"item_code": item.name,
		"item_name": item.item_name,
		"item_group": item.item_group,
		"brand": item.brand,
		"stock_uom": item.stock_uom,
		"has_batch_no": bool(item.has_batch_no),
		"batch_no": batch.name if batch else None,
		"barcode_uom": barcode_uom,
		"default_purchase_uom": item.purchase_uom,
		"purchase_uoms": purchase_uoms,
		"warehouse": warehouse,
		"current_qty": _balance(item.name, warehouse, batch.name if batch else None),
	}


@frappe.whitelist(methods=["POST"])
def receive_inventory(payload: dict | str) -> dict:
	frappe.has_permission("Purchase Receipt", ptype="create", throw=True)
	frappe.has_permission("Purchase Receipt", ptype="submit", throw=True)
	data = _payload(payload)
	item = _item(str(data.get("item_code") or ""))
	warehouse = str(data.get("warehouse") or "")
	company = _warehouse_company(warehouse)
	supplier = str(data.get("supplier") or "")
	if not supplier or not frappe.db.exists("Supplier", {"name": supplier, "disabled": 0}):
		frappe.throw(_("Choose an active Supplier."), frappe.ValidationError)

	purchase_uom = str(data.get("purchase_uom") or "")
	conversion_factor = _conversion_factor(item, purchase_uom)
	try:
		plan = plan_receipt(
			purchase_units=data.get("purchase_units"),
			conversion_factor=conversion_factor,
			unit_cost=data.get("unit_cost", 0),
			purchase_uom=purchase_uom,
			batched=bool(item.has_batch_no),
		)
	except DomainError as error:
		_throw_domain(error)
		raise

	before = _balance(item.name, warehouse)
	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	currency = frappe.get_cached_value("Company", company, "default_currency")
	receipt = frappe.new_doc("Purchase Receipt")
	receipt.company = company
	receipt.supplier = supplier
	receipt.posting_date = nowdate()
	receipt.posting_time = nowtime()
	receipt.set_posting_time = 1
	receipt.currency = currency
	receipt.conversion_rate = 1
	receipt.remarks = f"{APP_MARKER} scanner receipt"

	batch_names = []
	labels = []
	if item.has_batch_no:
		for _index in range(plan.physical_units):
			batch_no = _next_batch_name()
			batch = frappe.get_doc(
				{
					"doctype": "Batch",
					"batch_id": batch_no,
					"item": item.name,
					"supplier": supplier,
				}
			).insert()
			batch_names.append(batch.name)
			receipt.append(
				"items",
				{
					"item_code": item.name,
					"warehouse": warehouse,
					"qty": plan.quantity_per_batch,
					"received_qty": plan.quantity_per_batch,
					"stock_qty": plan.quantity_per_batch,
					"uom": item.stock_uom,
					"stock_uom": item.stock_uom,
					"conversion_factor": 1,
					"rate": plan.stock_rate,
					"cost_center": cost_center,
					"use_serial_batch_fields": 1,
					"batch_no": batch.name,
				},
			)
			labels.append(
				{
					"label_code": batch.name,
					"tracking": "Batch",
					"batch_no": batch.name,
					"item_code": item.name,
					"item_name": item.item_name,
					"stock_uom": item.stock_uom,
					"remaining": plan.quantity_per_batch,
				}
			)
	else:
		receipt.append(
			"items",
			{
				"item_code": item.name,
				"warehouse": warehouse,
				"qty": plan.purchase_units,
				"received_qty": plan.purchase_units,
				"stock_qty": plan.stock_quantity,
				"uom": purchase_uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": conversion_factor,
				"rate": flt(data.get("unit_cost")),
				"cost_center": cost_center,
			},
		)

	receipt.insert()
	receipt.submit()
	for batch_no in batch_names:
		frappe.db.set_value(
			"Batch",
			batch_no,
			{"reference_doctype": receipt.doctype, "reference_name": receipt.name},
			update_modified=False,
		)
	_mark_transaction(receipt, "receive", f"{item.name} +{plan.stock_quantity:g} {item.stock_uom}")
	return _result(
		receipt,
		item=item,
		warehouse=warehouse,
		batch_no=None,
		before=before,
		change=plan.stock_quantity,
		labels=labels,
	)


@frappe.whitelist(methods=["POST"])
def consume_inventory(payload: dict | str) -> dict:
	frappe.has_permission("Stock Entry", ptype="create", throw=True)
	frappe.has_permission("Stock Entry", ptype="submit", throw=True)
	data = _payload(payload)
	item = _item(str(data.get("item_code") or ""))
	warehouse = str(data.get("warehouse") or "")
	company = _warehouse_company(warehouse)
	batch_no = str(data.get("batch_no") or "") or None
	if item.has_batch_no and not batch_no:
		frappe.throw(_("Scan the unique Batch label on this roll."), frappe.ValidationError)
	if batch_no:
		_batch(batch_no, item.name)

	current = _balance(item.name, warehouse, batch_no)
	try:
		change = calculate_consumption(current=current, mode=str(data.get("mode") or ""), value=data.get("value"))
	except DomainError as error:
		_throw_domain(error)
		raise

	from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

	entry = make_stock_entry(
		item_code=item.name,
		qty=abs(change.change),
		company=company,
		from_warehouse=warehouse,
		purpose="Material Issue",
		batch_no=batch_no,
		use_serial_batch_fields=1 if batch_no else 0,
		do_not_submit=True,
	)
	entry.remarks = f"{APP_MARKER} scanner consumption"
	entry.save()
	entry.submit()
	_mark_transaction(entry, "consume", f"{item.name} {change.change:g} {item.stock_uom}")
	return _result(
		entry,
		item=item,
		warehouse=warehouse,
		batch_no=batch_no,
		before=change.before,
		change=change.change,
	)


def _adjustment_account(company: str) -> str:
	account = frappe.get_cached_value("Company", company, "stock_adjustment_account")
	if account:
		return account
	account = frappe.db.get_value("Account", {"company": company, "account_type": "Stock Adjustment", "is_group": 0})
	if account:
		return account
	account = frappe.db.get_value("Account", {"company": company, "account_type": "Temporary", "is_group": 0})
	if not account:
		frappe.throw(_("Configure a Stock Adjustment account for Company {0}.").format(company))
	return account


@frappe.whitelist(methods=["POST"])
def reconcile_inventory(payload: dict | str) -> dict:
	frappe.has_permission("Stock Reconciliation", ptype="create", throw=True)
	frappe.has_permission("Stock Reconciliation", ptype="submit", throw=True)
	data = _payload(payload)
	item = _item(str(data.get("item_code") or ""))
	warehouse = str(data.get("warehouse") or "")
	company = _warehouse_company(warehouse)
	batch_no = str(data.get("batch_no") or "") or None
	if item.has_batch_no and not batch_no:
		frappe.throw(_("Scan the unique Batch label on this roll."), frappe.ValidationError)
	if batch_no:
		_batch(batch_no, item.name)

	from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_stock_balance_for

	posting_date = nowdate()
	posting_time = nowtime()
	stock = get_stock_balance_for(
		item.name,
		warehouse,
		posting_date,
		posting_time,
		batch_no=batch_no,
		with_valuation_rate=True,
		row=frappe._dict(
			{
				"item_code": item.name,
				"warehouse": warehouse,
				"batch_no": batch_no,
				"use_serial_batch_fields": 1 if batch_no else 0,
				"current_qty": 0,
			}
		),
		company=company,
	)
	try:
		change = calculate_reconciliation(current=stock.get("qty", 0), actual=data.get("actual"))
	except DomainError as error:
		_throw_domain(error)
		raise

	reconciliation = frappe.new_doc("Stock Reconciliation")
	reconciliation.purpose = "Stock Reconciliation"
	reconciliation.posting_date = posting_date
	reconciliation.posting_time = posting_time
	reconciliation.set_posting_time = 1
	reconciliation.company = company
	reconciliation.expense_account = _adjustment_account(company)
	reconciliation.cost_center = frappe.get_cached_value("Company", company, "cost_center")
	reconciliation.append(
		"items",
		{
			"item_code": item.name,
			"warehouse": warehouse,
			"qty": change.after,
			"valuation_rate": stock.get("rate", 0),
			"batch_no": batch_no,
			"use_serial_batch_fields": 1 if batch_no else 0,
			"reconcile_all_serial_batch": 0 if batch_no else 1,
		},
	)
	reconciliation.insert()
	reconciliation.submit()
	reason = str(data.get("reason") or "Physical measurement")
	_mark_transaction(reconciliation, "count", f"{item.name} {change.change:g} {item.stock_uom}; {reason}")
	return _result(
		reconciliation,
		item=item,
		warehouse=warehouse,
		batch_no=batch_no,
		before=change.before,
		change=change.change,
	)


@frappe.whitelist(methods=["POST"])
def cancel_transaction(voucher_type: str, voucher_no: str) -> dict:
	if voucher_type not in TRANSACTION_DOCTYPES:
		frappe.throw(_("That document type cannot be cancelled from Studio Inventory."), frappe.ValidationError)
	doc = frappe.get_doc(voucher_type, voucher_no)
	doc.check_permission("cancel")
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted transaction can be cancelled."), frappe.ValidationError)
	if doc.owner != frappe.session.user:
		frappe.throw(_("Only the user who created this app transaction can undo it."), frappe.PermissionError)
	if (now_datetime() - doc.creation).total_seconds() > 15 * 60:
		frappe.throw(_("The 15-minute quick-undo window has expired. Cancel the document from ERPNext instead."))
	marker = frappe.db.exists(
		"Comment",
		{
			"reference_doctype": voucher_type,
			"reference_name": voucher_no,
			"content": ("like", f"%{APP_MARKER}%"),
		},
	)
	if not marker:
		frappe.throw(_("This transaction was not created by Studio Inventory."), frappe.PermissionError)

	doc.cancel()
	_mark_transaction(doc, "undo")
	return {"voucher_type": voucher_type, "voucher_no": voucher_no, "cancelled": True}


def _activity_item(item_code: str):
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	return item


def _activity_row(doc) -> dict | None:
	if doc.doctype == "Purchase Receipt" and doc.items:
		item = _activity_item(doc.items[0].item_code)
		change = sum(flt(row.stock_qty) for row in doc.items)
		detail = "Purchase Receipt"
	elif doc.doctype == "Stock Entry" and doc.items:
		item = _activity_item(doc.items[0].item_code)
		change = -sum(flt(row.transfer_qty) for row in doc.items if row.s_warehouse)
		detail = doc.purpose or "Stock Entry"
	elif doc.doctype == "Stock Reconciliation" and doc.items:
		item = _activity_item(doc.items[0].item_code)
		change = flt(doc.items[0].qty) - flt(doc.items[0].current_qty)
		detail = "Stock Reconciliation"
	else:
		return None

	return {
		"voucher_type": doc.doctype,
		"voucher_no": doc.name,
		"item_code": item.name,
		"item_name": item.item_name,
		"detail": detail,
		"change": change,
		"stock_uom": item.stock_uom,
		"creation": doc.creation,
		"owner": doc.owner,
		"cancelled": doc.docstatus == 2,
	}


@frappe.whitelist(methods=["POST"])
def get_recent_activity(limit: int = 30) -> list[dict]:
	limit = min(max(int(limit), 1), 100)
	comments = frappe.get_list(
		"Comment",
		filters={
			"content": ("like", f"%{APP_MARKER}%"),
			"reference_doctype": ("in", TRANSACTION_DOCTYPES),
		},
		fields=["reference_doctype", "reference_name", "creation"],
		order_by="creation desc",
		limit_page_length=limit * 2,
	)
	rows = []
	seen = set()
	for comment in comments:
		key = (comment.reference_doctype, comment.reference_name)
		if key in seen:
			continue
		seen.add(key)
		try:
			doc = frappe.get_doc(*key)
			if not doc.has_permission("read"):
				continue
			row = _activity_row(doc)
		except frappe.PermissionError:
			continue
		if row:
			rows.append(row)
		if len(rows) >= limit:
			break
	return rows


def _get_all_list(doctype: str, *, page_length: int = 500, **kwargs) -> list:
	rows = []
	start = 0
	while True:
		page = frappe.get_list(
			doctype,
			limit_start=start,
			limit_page_length=page_length,
			**kwargs,
		)
		rows.extend(page)
		if len(page) < page_length:
			return rows
		start += len(page)


def _get_all_rows(doctype: str, *, page_length: int = 500, **kwargs) -> list:
	rows = []
	start = 0
	while True:
		page = frappe.get_all(
			doctype,
			limit_start=start,
			limit_page_length=page_length,
			**kwargs,
		)
		rows.extend(page)
		if len(page) < page_length:
			return rows
		start += len(page)


def _inventory_label_items() -> list:
	return _get_all_list(
		"Item",
		filters={
			"disabled": 0,
			"is_stock_item": 1,
			"has_variants": 0,
			"item_group": "Paper",
			"stock_uom": ("in", ["Foot", "Sheet", "Card Set"]),
		},
		fields=["name", "item_name", "stock_uom"],
		order_by="item_name asc",
	)


def _internal_barcodes_by_item(item_names: list[str]) -> dict[str, str]:
	if not item_names:
		return {}
	rows = _get_all_rows(
		"Item Barcode",
		filters={"parent": ("in", item_names)},
		fields=["parent", "barcode", "idx"],
		order_by="parent asc, idx asc",
	)
	barcodes = {}
	for row in rows:
		if row.parent not in barcodes and INTERNAL_BARCODE_PATTERN.fullmatch((row.barcode or "").strip()):
			barcodes[row.parent] = row.barcode.strip()
	return barcodes


def _next_internal_barcode() -> str:
	for _attempt in range(100):
		barcode = make_autoname(INTERNAL_BARCODE_NAMING_SERIES)
		if not INTERNAL_BARCODE_PATTERN.fullmatch(barcode):
			frappe.throw(_("The internal barcode series has exhausted its six-digit capacity."))
		if not frappe.db.exists("Item Barcode", {"barcode": barcode}):
			return barcode
	frappe.throw(_("Could not allocate a unique internal inventory barcode."))
	return ""


@frappe.whitelist(methods=["POST"])
def get_inventory_labels(warehouse: str) -> list[dict]:
	_warehouse_company(warehouse)
	items = _inventory_label_items()
	internal_barcodes = _internal_barcodes_by_item([item.name for item in items])
	labels = []
	for item in items:
		internal_barcode = internal_barcodes.get(item.name)
		labels.append(
			{
				"label_code": internal_barcode or item.name,
				"has_internal_barcode": bool(internal_barcode),
				"tracking": "Item",
				"batch_no": None,
				"item_code": item.name,
				"item_name": item.item_name,
				"stock_uom": item.stock_uom,
				"remaining": _balance(item.name, warehouse),
			}
		)
	labels.sort(key=lambda label: (label["item_name"].casefold(), label["label_code"].casefold()))
	return labels


@frappe.whitelist(methods=["POST"])
def assign_missing_internal_barcodes(warehouse: str) -> dict:
	_warehouse_company(warehouse)
	frappe.has_permission("Item", ptype="write", throw=True)
	items = _inventory_label_items()
	internal_barcodes = _internal_barcodes_by_item([item.name for item in items])
	created = []
	for item in items:
		if item.name in internal_barcodes:
			continue
		doc = frappe.get_doc("Item", item.name)
		doc.check_permission("write")
		current = next(
			(
				row.barcode.strip()
				for row in doc.barcodes
				if INTERNAL_BARCODE_PATTERN.fullmatch((row.barcode or "").strip())
			),
			None,
		)
		if current:
			internal_barcodes[item.name] = current
			continue
		barcode = _next_internal_barcode()
		doc.append("barcodes", {"barcode": barcode})
		doc.save()
		internal_barcodes[item.name] = barcode
		created.append({"item_code": item.name, "barcode": barcode})

	return {
		"created": created,
		"existing": len(items) - len(created),
		"labels": get_inventory_labels(warehouse),
	}
