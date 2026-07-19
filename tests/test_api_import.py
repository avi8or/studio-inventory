import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class ApiImportTests(unittest.TestCase):
	def test_api_imports_with_frappe_v16_utils_surface(self):
		frappe = types.ModuleType("frappe")
		frappe.__path__ = []
		frappe._ = lambda value: value
		frappe.whitelist = lambda **_kwargs: lambda function: function
		frappe.ValidationError = type("ValidationError", (Exception,), {})
		frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
		frappe.PermissionError = type("PermissionError", (Exception,), {})

		frappe_model = types.ModuleType("frappe.model")
		frappe_model.__path__ = []
		frappe_naming = types.ModuleType("frappe.model.naming")
		frappe_naming.make_autoname = lambda _series: "SIB.000001"
		frappe_utils = types.ModuleType("frappe.utils")
		frappe_utils.flt = float
		frappe_utils.now_datetime = lambda: None
		frappe_utils.nowdate = lambda: None
		frappe_utils.nowtime = lambda: None

		modules = {
			"frappe": frappe,
			"frappe.model": frappe_model,
			"frappe.model.naming": frappe_naming,
			"frappe.utils": frappe_utils,
		}
		api_path = Path(__file__).parents[1] / "studio_inventory" / "api.py"
		spec = importlib.util.spec_from_file_location("studio_inventory_api_import_test", api_path)
		module = importlib.util.module_from_spec(spec)

		with patch.dict(sys.modules, modules):
			spec.loader.exec_module(module)

		warehouses = [
			types.SimpleNamespace(name="Finished Goods - LPS", warehouse_name="Finished Goods", company="Lightpress"),
			types.SimpleNamespace(name="Stores - LPS", warehouse_name="Stores", company="Lightpress"),
		]
		self.assertEqual(
			module._select_default_warehouse(warehouses, "Lightpress", "Finished Goods - LPS"),
			"Stores - LPS",
		)

		pages = {
			0: [types.SimpleNamespace(name="ITEM-001"), types.SimpleNamespace(name="ITEM-002")],
			2: [types.SimpleNamespace(name="ITEM-003")],
		}
		calls = []

		def get_list(doctype, *, limit_start, limit_page_length, **kwargs):
			calls.append((doctype, limit_start, limit_page_length, kwargs))
			return pages[limit_start]

		frappe.get_list = get_list
		self.assertEqual(
			[row.name for row in module._get_all_list("Item", page_length=2, fields=["name"])],
			["ITEM-001", "ITEM-002", "ITEM-003"],
		)
		self.assertEqual([call[1] for call in calls], [0, 2])

		roll = types.SimpleNamespace(
			name="P-HAHN-TORCHON-285-R-24",
			item_name="Hahnemühle — Torchon — 285 GSM — 24 in roll",
			stock_uom="Foot",
		)
		sheet = types.SimpleNamespace(
			name="P-HAHN-TORCHON-285-S-13X19",
			item_name="Hahnemühle — Torchon — 285 GSM — 13 × 19 in",
			stock_uom="Sheet",
		)
		batch = types.SimpleNamespace(name="SIB.000123", item=roll.name)

		def get_all_list(doctype, **kwargs):
			if doctype == "Batch":
				return [batch]
			return [roll] if kwargs["filters"]["has_batch_no"] else [sheet]

		module._warehouse_company = lambda warehouse: "Lightpress"
		module._get_all_list = get_all_list
		module._balance = lambda *_args, **_kwargs: 39.37

		labels = module.get_inventory_labels("Stores - LPS")
		roll_item_label = next(label for label in labels if label["label_code"] == roll.name)
		roll_batch_label = next(label for label in labels if label["label_code"] == batch.name)
		self.assertTrue(roll_item_label["receive_only"])
		self.assertEqual(roll_item_label["tracking"], "Item")
		self.assertFalse(roll_batch_label["receive_only"])


if __name__ == "__main__":
	unittest.main()
