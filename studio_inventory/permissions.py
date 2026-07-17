import frappe


def check_app_permission() -> bool:
	if frappe.session.user == "Guest":
		return False

	return any(
		frappe.has_permission(doctype, ptype="create") and frappe.has_permission(doctype, ptype="submit")
		for doctype in ("Purchase Receipt", "Stock Entry", "Stock Reconciliation")
	)
