import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class PricingApiAccessTests(unittest.TestCase):
	def load_module(self):
		frappe = types.ModuleType("frappe")
		frappe.__path__ = []
		frappe._ = lambda value: value
		frappe.whitelist = lambda **_kwargs: lambda function: function
		frappe.ValidationError = type("ValidationError", (Exception,), {})
		frappe.PermissionError = type("PermissionError", (Exception,), {})
		frappe.session = types.SimpleNamespace(user="pricing@example.com")
		frappe.get_roles = lambda: []
		frappe.has_permission = lambda *_args, **_kwargs: False

		frappe_utils = types.ModuleType("frappe.utils")
		frappe_utils.flt = float
		frappe_utils.get_url_to_list = lambda doctype: f"/app/{doctype.lower()}"
		frappe_utils.getdate = lambda value: value
		frappe_utils.nowdate = lambda: "2026-07-20"

		modules = {"frappe": frappe, "frappe.utils": frappe_utils}
		api_path = Path(__file__).parents[1] / "studio_inventory" / "pricing_api.py"
		spec = importlib.util.spec_from_file_location("studio_inventory_pricing_api_access_test", api_path)
		module = importlib.util.module_from_spec(spec)
		with patch.dict(sys.modules, modules):
			spec.loader.exec_module(module)
		return module, frappe

	def test_sales_roles_can_calculate_without_quotation_permission(self):
		module, frappe = self.load_module()
		frappe.get_roles = lambda: ["Sales User"]

		self.assertTrue(module.has_pricing_access())

	def test_existing_quotation_users_keep_pricing_access(self):
		module, frappe = self.load_module()
		frappe.has_permission = lambda doctype, *, ptype: doctype == "Quotation" and ptype == "create"

		self.assertTrue(module.has_pricing_access())

	def test_guests_and_unrelated_users_cannot_access_internal_pricing(self):
		module, frappe = self.load_module()
		self.assertFalse(module.has_pricing_access())

		frappe.session.user = "Guest"
		frappe.get_roles = lambda: ["Sales Manager"]
		self.assertFalse(module.has_pricing_access())

	def test_standalone_context_lists_only_supported_paper_items(self):
		module, frappe = self.load_module()
		captured = {}

		def get_list(doctype, **kwargs):
			captured.update({"doctype": doctype, **kwargs})
			return []

		frappe.get_list = get_list
		self.assertEqual(module._paper_options(), [])
		self.assertEqual(captured["doctype"], "Item")
		self.assertEqual(captured["filters"]["stock_uom"], ["in", ["Sheet", "Foot"]])
		self.assertEqual(captured["limit_page_length"], 1000)


if __name__ == "__main__":
	unittest.main()
