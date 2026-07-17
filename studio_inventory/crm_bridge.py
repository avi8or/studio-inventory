from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist(methods=["POST"])
def get_or_create_customer(quotation: str) -> str | None:
	if not frappe.db.exists("DocType", "CRM Deal"):
		return None
	frappe.get_doc("Quotation", quotation).check_permission("read")
	crm_deal = frappe.db.get_value("Quotation", quotation, "crm_deal")
	return _customer_for_deal(crm_deal) if crm_deal else None


def ensure_customer_from_quotation(doc, method: str | None = None) -> None:
	if doc.customer or not frappe.db.exists("DocType", "CRM Deal"):
		return
	quotation_names = list(
		dict.fromkeys(row.prevdoc_docname for row in doc.items if row.get("prevdoc_docname"))
	)
	for quotation_name in quotation_names:
		crm_deal = frappe.db.get_value("Quotation", quotation_name, "crm_deal")
		if not crm_deal:
			continue
		customer = _customer_for_deal(crm_deal)
		if customer:
			doc.customer = customer
			return


def _customer_for_deal(crm_deal: str) -> str:
	customer = frappe.db.get_value("Customer", {"crm_deal": crm_deal}, "name")
	if not customer:
		customer = frappe.db.get_value("CRM Deal", crm_deal, "erpnext_customer")
	if customer and frappe.db.exists("Customer", customer):
		return customer
	return _create_customer(crm_deal)


def _create_customer(crm_deal: str) -> str:
	frappe.has_permission("Customer", ptype="create", throw=True)
	deal = frappe.get_doc("CRM Deal", crm_deal)
	deal.check_permission("read")
	primary_contact = next((row for row in deal.contacts if row.is_primary), None)
	if deal.organization:
		customer_name = frappe.db.get_value("CRM Organization", deal.organization, "organization_name")
		customer_type = "Company"
	else:
		customer_name = primary_contact.full_name if primary_contact else deal.lead_name
		customer_type = "Individual"
	if not customer_name:
		frappe.throw(_("The CRM Deal needs an Organization or primary Contact before creating a Sales Order."))

	values = {
		"doctype": "Customer",
		"customer_name": customer_name,
		"customer_type": customer_type,
		"crm_deal": deal.name,
		"default_currency": deal.currency,
		"website": deal.website,
	}
	if deal.territory and frappe.db.exists("Territory", deal.territory):
		values["territory"] = deal.territory
	if deal.industry and frappe.db.exists("Industry Type", deal.industry):
		values["industry"] = deal.industry

	customer = frappe.get_doc(values)
	customer.insert()
	frappe.db.set_value("CRM Deal", deal.name, "erpnext_customer", customer.name, update_modified=False)
	_link_contacts_and_address(deal, customer.name)
	return customer.name


def _link_contacts_and_address(deal, customer: str) -> None:
	links = [("Contact", row.contact) for row in deal.contacts if row.contact]
	if deal.organization:
		address = frappe.db.get_value("CRM Organization", deal.organization, "address")
		if address:
			links.append(("Address", address))
	for index, (doctype, name) in enumerate(links):
		savepoint = f"studio_inventory_customer_link_{index}"
		frappe.db.savepoint(savepoint)
		try:
			doc = frappe.get_doc(doctype, name)
			if doc.has_link("Customer", customer):
				continue
			doc.append("links", {"link_doctype": "Customer", "link_name": customer})
			doc.save()
		except Exception:
			traceback = frappe.get_traceback()
			frappe.db.rollback(save_point=savepoint)
			frappe.log_error(
				traceback,
				f"Studio Inventory could not link {doctype} {name} to Customer {customer}",
			)
