import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class SetupImportTests(unittest.TestCase):
	def load_setup(self, *, conflict_doctype=None):
		updates = []
		clear_cache_calls = []

		class FakeDb:
			def exists(self, doctype, _filters):
				return "conflict" if doctype == conflict_doctype else None

			def set_value(self, doctype, name, values, *, update_modified):
				updates.append((doctype, name, values, update_modified))

		frappe = types.ModuleType("frappe")
		frappe.__path__ = []
		frappe.db = FakeDb()
		frappe.get_all = lambda *_args, **_kwargs: ["ROLL-24", "ROLL-44"]
		frappe.clear_cache = lambda **kwargs: clear_cache_calls.append(kwargs)
		frappe.throw = lambda message: (_ for _ in ()).throw(RuntimeError(message))

		custom_field = types.ModuleType("frappe.custom.doctype.custom_field.custom_field")
		custom_field.create_custom_fields = lambda *_args, **_kwargs: None
		property_setter = types.ModuleType("frappe.custom.doctype.property_setter.property_setter")
		property_setter.make_property_setter = lambda *_args, **_kwargs: None
		navigation = types.ModuleType("studio_inventory.navigation")
		navigation.ensure_stock_workspace_link = lambda: None

		modules = {
			"frappe": frappe,
			"frappe.custom": types.ModuleType("frappe.custom"),
			"frappe.custom.doctype": types.ModuleType("frappe.custom.doctype"),
			"frappe.custom.doctype.custom_field": types.ModuleType("frappe.custom.doctype.custom_field"),
			"frappe.custom.doctype.custom_field.custom_field": custom_field,
			"frappe.custom.doctype.property_setter": types.ModuleType(
				"frappe.custom.doctype.property_setter"
			),
			"frappe.custom.doctype.property_setter.property_setter": property_setter,
			"studio_inventory.navigation": navigation,
		}
		setup_path = Path(__file__).parents[1] / "studio_inventory" / "setup.py"
		spec = importlib.util.spec_from_file_location("studio_inventory_setup_import_test", setup_path)
		module = importlib.util.module_from_spec(spec)
		with patch.dict(sys.modules, modules):
			spec.loader.exec_module(module)
		return module, updates, clear_cache_calls

	def test_migrates_paper_rolls_to_reusable_item_tracking(self):
		module, updates, clear_cache_calls = self.load_setup()

		module._migrate_paper_rolls_to_item_tracking()

		self.assertEqual([update[1] for update in updates], ["ROLL-24", "ROLL-44"])
		self.assertTrue(all(update[2]["has_batch_no"] == 0 for update in updates))
		self.assertTrue(all(update[2]["create_new_batch"] == 0 for update in updates))
		self.assertEqual(clear_cache_calls, [{"doctype": "Item"}])

	def test_refuses_migration_when_batch_history_exists(self):
		module, updates, clear_cache_calls = self.load_setup(conflict_doctype="Batch")

		with self.assertRaisesRegex(RuntimeError, "cannot be disabled"):
			module._migrate_paper_rolls_to_item_tracking()

		self.assertEqual(updates, [])
		self.assertEqual(clear_cache_calls, [])

	def test_crm_action_opens_save_nothing_price_calculator(self):
		module, _updates, _clear_cache_calls = self.load_setup()

		script = module._crm_deal_form_script()

		self.assertIn('label: __("Price Calculator")', script)
		self.assertIn('window.open("/studio-inventory?mode=price", "_blank")', script)
		self.assertIn('label: __("Create Print Quotation")', script)


if __name__ == "__main__":
	unittest.main()
