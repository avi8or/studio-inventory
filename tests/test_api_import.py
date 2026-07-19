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
		frappe.has_permission = lambda *_args, **_kwargs: True
		frappe.ValidationError = type("ValidationError", (Exception,), {})
		frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
		frappe.PermissionError = type("PermissionError", (Exception,), {})

		frappe_model = types.ModuleType("frappe.model")
		frappe_model.__path__ = []
		frappe_naming = types.ModuleType("frappe.model.naming")
		frappe_naming.make_autoname = lambda series: "INV000043" if series == "INV.######" else "SIB.000001"
		frappe_utils = types.ModuleType("frappe.utils")
		frappe_utils.cint = lambda value: int(value)
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
		card = types.SimpleNamespace(
			name="P-HAHN-BAMBOO-290-C-5X7",
			item_name="Hahnemühle — Bamboo — 290 GSM — 5 × 7 in cards",
			stock_uom="Card Set",
		)
		queried_doctypes = []

		def get_all_list(doctype, **kwargs):
			queried_doctypes.append(doctype)
			self.assertEqual(kwargs["filters"]["item_group"], "Paper")
			return [roll, sheet]

		module._warehouse_company = lambda warehouse: "Lightpress"
		module._get_all_list = get_all_list
		module._balance = lambda *_args, **_kwargs: 39.37
		frappe.get_all = lambda doctype, **_kwargs: [
			types.SimpleNamespace(parent=roll.name, barcode="P-HAHN-TORCHON-285-R-24", idx=1),
			types.SimpleNamespace(parent=roll.name, barcode="INV000042", idx=2),
		] if doctype == "Item Barcode" else []

		labels = module.get_inventory_labels("Stores - LPS")
		roll_item_label = next(label for label in labels if label["item_code"] == roll.name)
		sheet_item_label = next(label for label in labels if label["item_code"] == sheet.name)
		self.assertEqual(queried_doctypes, ["Item"])
		self.assertEqual(len(labels), 2)
		self.assertEqual(roll_item_label["tracking"], "Item")
		self.assertEqual(roll_item_label["label_code"], "INV000042")
		self.assertTrue(roll_item_label["has_internal_barcode"])
		self.assertEqual(sheet_item_label["label_code"], sheet.name)
		self.assertFalse(sheet_item_label["has_internal_barcode"])

		class ItemDoc:
			def __init__(self, name):
				self.name = name
				self.barcodes = []
				self.saved = False

			def check_permission(self, permission):
				self.checked_permission = permission

			def append(self, fieldname, value):
				self.appended_fieldname = fieldname
				self.barcodes.append(types.SimpleNamespace(**value))

			def save(self):
				self.saved = True

		sheet_doc = ItemDoc(sheet.name)
		module._inventory_label_items = lambda: [roll, sheet, card]
		module._internal_barcodes_by_item = lambda _names: {roll.name: "INV000042"}
		module._next_internal_barcode = lambda: "INV000043"
		frappe.get_doc = lambda doctype, name: sheet_doc if (doctype, name) == ("Item", sheet.name) else None

		assignment = module.assign_missing_internal_barcodes("Stores - LPS", limit=1)
		self.assertEqual(assignment["created"], [{"item_code": sheet.name, "barcode": "INV000043"}])
		self.assertEqual(assignment["assigned"], 2)
		self.assertEqual(assignment["remaining"], 1)
		self.assertEqual(assignment["total"], 3)
		self.assertEqual(sheet_doc.checked_permission, "write")
		self.assertEqual(sheet_doc.appended_fieldname, "barcodes")
		self.assertEqual(sheet_doc.barcodes[0].barcode, "INV000043")
		self.assertTrue(sheet_doc.saved)


if __name__ == "__main__":
	unittest.main()
