import importlib.util
import json
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

	def test_pricing_basis_uses_the_smallest_costed_sibling_that_fits(self):
		module, frappe = self.load_module()
		settings = types.SimpleNamespace(paper_cost_price_list="Standard Buying")
		items = {
			width: types.SimpleNamespace(
				name=f"PAPER-{width}",
				item_name=f"Paper {width} inch roll",
				stock_uom="Foot",
				variant_of="PAPER-ROLL-TEMPLATE",
			)
			for width in (17, 24, 44)
		}
		bases = {
			17: {"item_code": "PAPER-17", "cost_per_sq_in": 0.024},
			24: {"item_code": "PAPER-24", "cost_per_sq_in": 0.0227},
			44: {"item_code": "PAPER-44", "cost_per_sq_in": 0.0222},
		}
		frappe.get_list = lambda *_args, **_kwargs: [
			types.SimpleNamespace(name=item.name)
			for item in items.values()
		]
		frappe.get_doc = lambda _doctype, name: next(
			item for item in items.values() if item.name == name
		)
		module._item_dimensions = lambda item: module.PaperDimensions(
			stock_uom="Foot",
			width_in=float(item.name.removeprefix("PAPER-")),
		)
		module._cost_basis = lambda item, _settings: bases[int(item.name.removeprefix("PAPER-"))]

		from_24 = module._pricing_cost_basis(
			items[24],
			settings=settings,
			finished_width_in=20,
			finished_height_in=24,
			selected_basis=bases[24],
		)
		from_44 = module._pricing_cost_basis(
			items[44],
			settings=settings,
			finished_width_in=20,
			finished_height_in=24,
			selected_basis=bases[44],
		)

		self.assertEqual(from_24["item_code"], "PAPER-24")
		self.assertEqual(from_44["item_code"], "PAPER-24")
		self.assertEqual(from_24["cost_per_sq_in"], from_44["cost_per_sq_in"])

	def test_calculation_separates_pricing_basis_from_actual_stock_cost(self):
		module, _frappe = self.load_module()
		settings = types.SimpleNamespace(default_print_item="PRINT-SERVICE")
		print_item = types.SimpleNamespace(name="PRINT-SERVICE", item_name="Custom Print")
		paper_item = types.SimpleNamespace(
			name="PAPER-44",
			item_name="Paper 44 inch roll",
			stock_uom="Foot",
		)
		dimensions = module.PaperDimensions(stock_uom="Foot", width_in=44)
		actual_basis = {
			"item_code": "PAPER-44",
			"item_name": "Paper 44 inch roll",
			"cost_per_sq_in": 0.02,
		}
		pricing_basis = {
			"item_code": "PAPER-24",
			"item_name": "Paper 24 inch roll",
			"cost_per_sq_in": 0.01,
		}
		module._active_pricing_model = lambda _settings: None
		module._print_item = lambda _item_code: print_item
		module._paper_item = lambda _item_code: paper_item
		module._item_dimensions = lambda _item: dimensions
		module._cost_basis = lambda _item, _settings: actual_basis
		module._pricing_cost_basis = lambda *_args, **_kwargs: pricing_basis
		module._rules = lambda *_args, **_kwargs: module.PricingRules()

		result = module._calculation_payload(
			{
				"print_item": "PRINT-SERVICE",
				"paper_item": "PAPER-44",
				"artwork_width_in": 8,
				"artwork_height_in": 10,
				"border_in": 0,
				"quantity": 1,
				"time_minutes": 0,
			},
			settings=settings,
		)
		snapshot = json.loads(result["snapshot"])

		self.assertEqual(result["paper_cost_per_sq_in"], 0.02)
		self.assertEqual(result["pricing_paper_cost_per_sq_in"], 0.01)
		self.assertEqual(result["pricing_cost_source"]["item_code"], "PAPER-24")
		self.assertEqual(result["calculation"]["unit_paper_cost"], 0.8)
		self.assertEqual(result["calculation"]["actual_unit_paper_cost"], 10.56)
		self.assertEqual(snapshot["inputs"]["paper_cost_per_sq_in"], 0.02)
		self.assertEqual(snapshot["inputs"]["pricing_paper_cost_per_sq_in"], 0.01)

	def test_snapshot_pricing_cost_falls_back_for_formula_version_two(self):
		module, _frappe = self.load_module()
		row = types.SimpleNamespace(si_paper_cost_per_sq_in=0.02)

		self.assertEqual(
			module._snapshot_pricing_cost(
				row,
				{"inputs": {"pricing_paper_cost_per_sq_in": 0.01}},
			),
			0.01,
		)
		self.assertEqual(
			module._snapshot_pricing_cost(row, {"inputs": {}}),
			0.02,
		)

	def test_estimate_validation_keeps_pricing_and_actual_stock_cost_separate(self):
		module, _frappe = self.load_module()
		captured = {}

		class Row(types.SimpleNamespace):
			def get(self, name):
				return getattr(self, name, None)

		class Estimate:
			def __init__(self, row):
				self.items = [row]
				self.recalculated = False

			def calculate_taxes_and_totals(self):
				self.recalculated = True

		row = Row(
			si_is_calculated_print=1,
			si_paper_item="PAPER-44",
			si_artwork_width_in=8,
			si_artwork_height_in=10,
			si_border_in=0,
			qty=1,
			si_time_minutes=0,
			si_ink_cost_per_sq_in=0.012,
			si_paper_cost_per_sq_in=0.02,
			discount_percentage=0,
			discount_amount=0,
		)
		snapshot = {
			"pricing_model": None,
			"inputs": {"pricing_paper_cost_per_sq_in": 0.01},
			"rules": module.asdict(module.PricingRules()),
			"price_adjustments": [],
			"matched_rules": [],
		}
		estimate = Estimate(row)
		module._pricing_settings = lambda: types.SimpleNamespace()
		module._paper_item = lambda _item_code: types.SimpleNamespace()
		module._item_dimensions = lambda _item: module.PaperDimensions(stock_uom="Foot", width_in=44)
		module._stored_snapshot = lambda _row: snapshot
		original_consumed_paper_cost = module.consumed_paper_cost
		original_calculate_print_price = module.calculate_print_price

		def consumed_paper_cost(**kwargs):
			captured["actual_rate"] = kwargs["paper_cost_per_sq_in"]
			return original_consumed_paper_cost(**kwargs)

		def calculate_print_price(**kwargs):
			captured["pricing_rate"] = kwargs["paper_cost_per_sq_in"]
			return original_calculate_print_price(**kwargs)

		module.consumed_paper_cost = consumed_paper_cost
		module.calculate_print_price = calculate_print_price

		module.validate_quotation(estimate)

		self.assertEqual(captured, {"actual_rate": 0.02, "pricing_rate": 0.01})
		self.assertTrue(estimate.recalculated)

	def test_existing_calculation_snapshot_freezes_its_model_values(self):
		module, _frappe = self.load_module()
		row = types.SimpleNamespace(si_paper_cost_per_sq_in=0.01)
		snapshot = {
			"rules": {
				"material_markup": 3,
			},
			"price_adjustments": [
				{
					"rule_name": "Stored floor",
					"priority": 10,
					"target": "minimum_unit_price",
					"operation": "set",
					"value": 20,
				}
			],
			"matched_rules": [{"rule_name": "Stored floor"}],
		}
		module._active_pricing_model = lambda _settings: self.fail("active model should not be loaded")

		resolution = module._row_pricing_resolution(
			row,
			types.SimpleNamespace(),
			types.SimpleNamespace(),
			snapshot,
		)

		self.assertEqual(resolution.rules.material_markup, 3)
		self.assertEqual(resolution.price_adjustments[0].value, 20)
		self.assertEqual(resolution.matched_rules[0]["rule_name"], "Stored floor")

	def test_create_estimate_builds_a_native_quotation_with_the_calculated_item(self):
		module, frappe = self.load_module()
		captured = {}

		class Quotation:
			name = "QTN-0001"

			def insert(self):
				captured["inserted"] = True
				return self

			def get_url(self):
				return "/app/quotation/QTN-0001"

		frappe.has_permission = lambda doctype, *, ptype: doctype == "Quotation" and ptype == "create"
		frappe.get_doc = lambda values: captured.update({"values": values}) or Quotation()
		module._check_pricing_permission = lambda: None
		module._payload = lambda payload: payload
		module._calculation_payload = lambda payload: {"calculation": payload}
		module._deal_quote_context = lambda crm_deal: {
			"quotation_to": "CRM Deal",
			"party_name": crm_deal,
		}
		module._calculated_estimate_item = lambda result: {
			"item_code": "PRINT-SERVICE",
			"rate": result["calculation"]["price"],
		}

		created = module.create_estimate({"price": 20}, "CRM-DEAL-0001")

		self.assertTrue(captured["inserted"])
		self.assertEqual(captured["values"]["doctype"], "Quotation")
		self.assertEqual(captured["values"]["party_name"], "CRM-DEAL-0001")
		self.assertEqual(captured["values"]["items"][0]["rate"], 20)
		self.assertEqual(created, {"name": "QTN-0001", "url": "/app/quotation/QTN-0001"})


if __name__ == "__main__":
	unittest.main()
