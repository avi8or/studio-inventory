import frappe


PRICING_USER_ROLES = {"Sales User", "Sales Manager", "System Manager"}


def has_pricing_access() -> bool:
	if frappe.session.user == "Guest":
		return False
	return bool(PRICING_USER_ROLES.intersection(frappe.get_roles())) or bool(
		frappe.has_permission("Quotation", ptype="create")
		or frappe.has_permission("Quotation", ptype="write")
	)


def check_app_permission() -> bool:
	if frappe.session.user == "Guest":
		return False

	return has_pricing_access() or any(
		frappe.has_permission(doctype, ptype="create") and frappe.has_permission(doctype, ptype="submit")
		for doctype in ("Purchase Receipt", "Stock Entry", "Stock Reconciliation")
	)
