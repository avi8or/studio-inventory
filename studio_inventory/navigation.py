from __future__ import annotations

from typing import Any


STOCK_SIDEBAR = "Stock"
APP_LABEL = "Studio Inventory"
APP_URL = "/studio-inventory"


def ensure_stock_workspace_link() -> None:
	import frappe

	if not frappe.db.exists("Workspace Sidebar", STOCK_SIDEBAR):
		return

	sidebar = frappe.get_doc("Workspace Sidebar", STOCK_SIDEBAR)
	items = list(sidebar.get("items") or [])
	matches = [item for item in items if _is_app_link(item)]
	changed = False

	if matches:
		app_link = matches[0]
		if len(matches) > 1:
			items = [item for item in items if item is app_link or not _is_app_link(item)]
			changed = True
	else:
		app_link = sidebar.append("items", {})
		items.append(app_link)
		changed = True

	expected = {
		"label": APP_LABEL,
		"type": "Link",
		"link_type": "URL",
		"url": APP_URL,
		"icon": "scan-barcode",
		"child": 0,
		"collapsible": 1,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	}
	for fieldname, value in expected.items():
		if getattr(app_link, fieldname, None) != value:
			setattr(app_link, fieldname, value)
			changed = True

	items.remove(app_link)
	home_index = next((index for index, item in enumerate(items) if item.label == "Home"), -1)
	items.insert(home_index + 1, app_link)
	if list(sidebar.get("items") or []) != items:
		changed = True

	for index, item in enumerate(items, start=1):
		if getattr(item, "idx", None) != index:
			item.idx = index
			changed = True

	if changed:
		sidebar.items = items
		sidebar.save(ignore_permissions=True)


def _is_app_link(item: Any) -> bool:
	return getattr(item, "label", None) == APP_LABEL or getattr(item, "url", None) == APP_URL
