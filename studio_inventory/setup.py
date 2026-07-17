from __future__ import annotations

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


CRM_FORM_SCRIPT_NAME = "Create Print Quotation"


def install() -> None:
	_apply_setup()


def after_migrate() -> None:
	_apply_setup()


def _apply_setup() -> None:
	_create_fields()
	_enable_crm_deal_quotations()
	_create_crm_form_script()


def _create_fields() -> None:
	fields = {
		"Quotation Item": [
			{
				"fieldname": "si_is_calculated_print",
				"fieldtype": "Check",
				"label": "Calculated Print",
				"default": "0",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "description",
			},
			{
				"fieldname": "si_paper_item",
				"fieldtype": "Link",
				"label": "Paper Item",
				"options": "Item",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_is_calculated_print",
			},
			{
				"fieldname": "si_artwork_width_in",
				"fieldtype": "Float",
				"label": "Artwork Width (in)",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_paper_item",
			},
			{
				"fieldname": "si_artwork_height_in",
				"fieldtype": "Float",
				"label": "Artwork Height (in)",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_artwork_width_in",
			},
			{
				"fieldname": "si_border_in",
				"fieldtype": "Float",
				"label": "Border (in)",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_artwork_height_in",
			},
			{
				"fieldname": "si_time_minutes",
				"fieldtype": "Float",
				"label": "Production Time (minutes)",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_border_in",
			},
			{
				"fieldname": "si_ink_cost_per_sq_in",
				"fieldtype": "Currency",
				"label": "Ink Cost per Square Inch",
				"precision": "6",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_time_minutes",
			},
			{
				"fieldname": "si_paper_cost_per_sq_in",
				"fieldtype": "Currency",
				"label": "Paper Cost per Square Inch",
				"precision": "6",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_ink_cost_per_sq_in",
			},
			{
				"fieldname": "si_cost_override",
				"fieldtype": "Check",
				"label": "Paper Cost Override",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_paper_cost_per_sq_in",
			},
			{
				"fieldname": "si_cost_source",
				"fieldtype": "Small Text",
				"label": "Paper Cost Source",
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_cost_override",
			},
			{
				"fieldname": "si_estimated_stock_qty",
				"fieldtype": "Float",
				"label": "Estimated Paper Quantity",
				"read_only": 1,
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_cost_source",
			},
			{
				"fieldname": "si_estimated_stock_uom",
				"fieldtype": "Link",
				"label": "Estimated Paper UOM",
				"options": "UOM",
				"read_only": 1,
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_estimated_stock_qty",
			},
			{
				"fieldname": "si_internal_cost",
				"fieldtype": "Currency",
				"label": "Internal Cost",
				"read_only": 1,
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_estimated_stock_uom",
			},
			{
				"fieldname": "si_gross_margin_pct",
				"fieldtype": "Percent",
				"label": "Gross Margin",
				"read_only": 1,
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_internal_cost",
			},
			{
				"fieldname": "si_formula_version",
				"fieldtype": "Data",
				"label": "Pricing Formula Version",
				"read_only": 1,
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_gross_margin_pct",
			},
			{
				"fieldname": "si_calculation_snapshot",
				"fieldtype": "Long Text",
				"label": "Calculation Snapshot",
				"read_only": 1,
				"hidden": 1,
				"print_hide": 1,
				"insert_after": "si_formula_version",
			},
		],
		"Item Price": [
			{
				"fieldname": "si_merchant_url",
				"fieldtype": "Data",
				"label": "Merchant URL",
				"options": "URL",
				"insert_after": "supplier",
			},
			{
				"fieldname": "si_last_verified_on",
				"fieldtype": "Date",
				"label": "Price Last Verified",
				"insert_after": "si_merchant_url",
			},
		],
	}
	# Frappe's document mapper copies same-named custom fields from Quotation Item
	# to Sales Order Item. Keeping the specification on both rows lets production
	# use the accepted quote without creating a second quote or calculator record.
	fields["Sales Order Item"] = [dict(field) for field in fields["Quotation Item"]]
	if frappe.db.exists("DocType", "CRM Deal"):
		fields["CRM Deal"] = [
			{
				"fieldname": "erpnext_customer",
				"fieldtype": "Data",
				"label": "Customer in ERPNext",
				"read_only": 1,
				"insert_after": "lead_name",
			}
		]
		fields["Quotation"] = [
			{
				"fieldname": "crm_deal",
				"fieldtype": "Data",
				"label": "Frappe CRM Deal",
				"read_only": 1,
				"print_hide": 1,
				"insert_after": "party_name",
			}
		]
		fields["Customer"] = [
			{
				"fieldname": "crm_deal",
				"fieldtype": "Data",
				"label": "Frappe CRM Deal",
				"read_only": 1,
				"print_hide": 1,
				"insert_after": "prospect_name",
			}
		]
	create_custom_fields(fields, ignore_validate=True)


def _enable_crm_deal_quotations() -> None:
	if not frappe.db.exists("DocType", "CRM Deal"):
		return
	property_name = "Quotation-quotation_to-link_filters"
	filters = frappe.db.get_value("Property Setter", property_name, "value")
	try:
		parsed = json.loads(filters) if filters else []
	except (TypeError, ValueError):
		parsed = []
	allowed = ["Customer", "Lead", "Prospect"]
	if (
		len(parsed) == 1
		and isinstance(parsed[0], list)
		and len(parsed[0]) >= 4
		and parsed[0][:3] == ["DocType", "name", "in"]
		and isinstance(parsed[0][3], list)
	):
		allowed = list(dict.fromkeys(parsed[0][3]))
	if "CRM Deal" not in allowed:
		allowed.append("CRM Deal")
	expected = [["DocType", "name", "in", allowed]]
	if parsed == expected:
		return
	make_property_setter(
		doctype="Quotation",
		fieldname="quotation_to",
		property="link_filters",
		value=json.dumps(expected),
		property_type="JSON",
		validate_fields_for_doctype=False,
	)


def _create_crm_form_script() -> None:
	if not frappe.db.exists("DocType", "CRM Form Script"):
		return
	script = """class CRMDeal {
	onLoad() {
		if (this.doc.__newDocument) return
		this.actions = this.actions || []
		if (this.actions.some((action) => action.label === __(\"Create Print Quotation\"))) return
		this.actions.push({
			label: __(\"Create Print Quotation\"),
			icon: \"file-text\",
			onClick: () => {
				call(\"studio_inventory.pricing_api.get_quotation_url\", {
					crm_deal: this.doc.name,
				}).then((url) => {
					if (url) window.open(url, \"_blank\")
				}).catch((error) => {
					toast.error(error.messages?.[0] || __(\"Could not create the quotation.\"))
				})
			},
		})
	}
}
"""
	if frappe.db.exists("CRM Form Script", CRM_FORM_SCRIPT_NAME):
		frappe.db.set_value(
			"CRM Form Script",
			CRM_FORM_SCRIPT_NAME,
			{"script": script, "enabled": 1},
			update_modified=False,
		)
		return
	frappe.get_doc(
		{
			"doctype": "CRM Form Script",
			"name": CRM_FORM_SCRIPT_NAME,
			"dt": "CRM Deal",
			"view": "Form",
			"script": script,
			"enabled": 1,
			"is_standard": 1,
		}
	).insert(ignore_permissions=True)
