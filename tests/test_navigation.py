import sys
import types
import unittest
from unittest.mock import patch

from studio_inventory.navigation import APP_URL, ensure_stock_workspace_link


class FakeSidebar:
	def __init__(self, items):
		self.items = items
		self.save_calls = 0

	def get(self, fieldname):
		return getattr(self, fieldname)

	def append(self, fieldname, values):
		item = types.SimpleNamespace(**values)
		getattr(self, fieldname).append(item)
		return item

	def save(self, *, ignore_permissions):
		self.save_calls += 1
		self.ignore_permissions = ignore_permissions


def item(label, *, link_type="DocType", url=None, idx=0):
	return types.SimpleNamespace(label=label, link_type=link_type, url=url, idx=idx)


class StockWorkspaceNavigationTests(unittest.TestCase):
	def run_setup(self, sidebar):
		frappe = types.ModuleType("frappe")
		frappe.db = types.SimpleNamespace(exists=lambda doctype, name: True)
		frappe.get_doc = lambda doctype, name: sidebar
		with patch.dict(sys.modules, {"frappe": frappe}):
			ensure_stock_workspace_link()

	def test_adds_scanner_immediately_after_home(self):
		sidebar = FakeSidebar([item("Home", idx=1), item("Dashboard", idx=2)])

		self.run_setup(sidebar)

		self.assertEqual([row.label for row in sidebar.items], ["Home", "Studio Inventory", "Dashboard"])
		self.assertEqual(sidebar.items[1].link_type, "URL")
		self.assertEqual(sidebar.items[1].url, APP_URL)
		self.assertEqual(sidebar.items[1].icon, "scan-barcode")
		self.assertEqual([row.idx for row in sidebar.items], [1, 2, 3])
		self.assertEqual(sidebar.save_calls, 1)
		self.assertTrue(sidebar.ignore_permissions)

	def test_existing_correct_link_does_not_rewrite_sidebar(self):
		home = item("Home", idx=1)
		app_link = item("Studio Inventory", link_type="URL", url=APP_URL, idx=2)
		app_link.type = "Link"
		app_link.icon = "scan-barcode"
		app_link.child = 0
		app_link.collapsible = 1
		app_link.indent = 0
		app_link.keep_closed = 0
		app_link.show_arrow = 0
		dashboard = item("Dashboard", idx=3)
		sidebar = FakeSidebar([home, app_link, dashboard])

		self.run_setup(sidebar)

		self.assertEqual(sidebar.save_calls, 0)


if __name__ == "__main__":
	unittest.main()
