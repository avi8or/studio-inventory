import frappe
from frappe import _

from studio_inventory.permissions import check_app_permission

no_cache = 1


def get_context():
	if not check_app_permission():
		frappe.throw(_("You do not have permission to access Studio Inventory"), frappe.PermissionError)

	context = frappe._dict()
	context.boot = frappe._dict(
		{
			"csrf_token": frappe.sessions.get_csrf_token(),
			"site_name": frappe.local.site,
			"user": frappe.session.user,
		}
	)
	return context
