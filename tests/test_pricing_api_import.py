import importlib.util
import sys
import types
import unittest
from datetime import date
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
		frappe_utils.cint = lambda value: int(value)
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

	def test_standalone_context_lists_all_supported_paper_items(self):
		module, frappe = self.load_module()
		captured = {}

		def get_list(doctype, **kwargs):
			captured.update({"doctype": doctype, **kwargs})
			return []

		frappe.get_list = get_list
		self.assertEqual(module._paper_options(), [])
		self.assertEqual(captured["doctype"], "Item")
		self.assertEqual(captured["filters"]["stock_uom"], ["in", ["Sheet", "Foot"]])
		self.assertEqual(captured["limit_page_length"], 0)

	def test_only_standalone_context_queries_paper_items(self):
		module, frappe = self.load_module()
		settings = types.SimpleNamespace(default_print_item="PRINT-SERVICE")
		rules = types.SimpleNamespace(ink_cost_per_sq_in=0.001, low_margin_threshold_pct=50)
		paper_calls = []

		module._check_pricing_permission = lambda: None
		module._pricing_settings = lambda: settings
		module._rules = lambda _settings: rules
		module._company = lambda _settings: "Lightpress"
		module._paper_cost_price_list = lambda _settings: "Standard Buying"
		module._can_override_cost = lambda: False
		module._paper_options = lambda: paper_calls.append(True) or [{"name": "PAPER-001"}]
		frappe.db = types.SimpleNamespace(get_value=lambda *_args: "USD")

		quotation_context = module.get_pricing_context()
		self.assertNotIn("paper_items", quotation_context)
		self.assertEqual(paper_calls, [])

		standalone_context = module.get_pricing_context(include_paper_items=True)
		self.assertEqual(standalone_context["paper_items"], [{"name": "PAPER-001"}])
		self.assertEqual(paper_calls, [True])

	def test_cost_basis_serializes_last_verified_date(self):
		module, frappe = self.load_module()

		class Row(dict):
			__getattr__ = dict.__getitem__

		frappe.db = types.SimpleNamespace(has_column=lambda *_args: True)
		frappe.get_list = lambda *_args, **_kwargs: [
			Row(
				name="PRICE-001",
				price_list="Standard Buying",
				price_list_rate=211.05,
				uom="Foot",
				supplier="Red River",
				valid_from=None,
				valid_upto=None,
				note=None,
				si_merchant_url=None,
				si_last_verified_on=date(2026, 7, 20),
			)
		]
		module._item_dimensions = lambda _item: module.PaperDimensions(stock_uom="Foot", width_in=24)
		item = types.SimpleNamespace(name="PAPER-001", stock_uom="Foot", uoms=[])
		settings = types.SimpleNamespace(paper_cost_price_list="Standard Buying")

		basis = module._cost_basis(item, settings)

		self.assertEqual(basis["last_verified_on"], "2026-07-20")


if __name__ == "__main__":
	unittest.main()
