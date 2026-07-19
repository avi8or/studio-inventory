import importlib.util
import sys
import types
import unittest
from datetime import date
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

		class NamingSeries:
			values = {}

			def __init__(self, series):
				self.series = series

			def get_current_value(self):
				return self.values.get(self.series, 0)

			def update_counter(self, value):
				self.values[self.series] = value

		frappe_naming.NamingSeries = NamingSeries
		frappe_naming.make_autoname = lambda series: "LP000043" if series == "LP.######" else "SIB.000001"
		frappe_utils = types.ModuleType("frappe.utils")
		frappe_utils.cint = lambda value: int(value)
		frappe_utils.flt = float
		frappe_utils.getdate = lambda value: value if isinstance(value, date) else date.fromisoformat(value)
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

		frappe.get_cached_doc = lambda doctype: types.SimpleNamespace(internal_barcode_prefix="LP")

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
			brand="Hahnemühle",
			variant_of="P-HAHN-TORCHON-285",
		)
		sheet = types.SimpleNamespace(
			name="P-HAHN-TORCHON-285-S-13X19",
			item_name="Hahnemühle — Torchon — 285 GSM — 13 × 19 in",
			stock_uom="Sheet",
			brand="Hahnemühle",
			variant_of="P-HAHN-TORCHON-285",
		)
		card = types.SimpleNamespace(
			name="P-HAHN-BAMBOO-290-C-5X7",
			item_name="Hahnemühle — Bamboo — 290 GSM — 5 × 7 in cards",
			stock_uom="Card Set",
			brand="Hahnemühle",
			variant_of="P-HAHN-BAMBOO-290",
		)
		torchon_template = types.SimpleNamespace(
			name="P-HAHN-TORCHON-285",
			item_name="Hahnemühle — Torchon — 285 GSM — Roll",
			brand="Hahnemühle",
		)
		queried_doctypes = []

		def get_all_list(doctype, **kwargs):
			queried_doctypes.append(doctype)
			if kwargs["filters"].get("item_group") == "Paper":
				return [roll, sheet]
			self.assertEqual(kwargs["filters"]["name"], ("in", ["P-HAHN-TORCHON-285"]))
			return [torchon_template]

		module._warehouse_company = lambda warehouse: "Lightpress"
		module._get_all_list = get_all_list
		module._balance = lambda *_args, **_kwargs: 39.37
		def get_all(doctype, **_kwargs):
			if doctype == "Item Barcode":
				return [
					types.SimpleNamespace(parent=roll.name, barcode="P-HAHN-TORCHON-285-R-24", idx=1),
					types.SimpleNamespace(parent=roll.name, barcode="LP000042", idx=2),
					types.SimpleNamespace(parent=sheet.name, barcode="INV000043", idx=1),
				]
			if doctype == "Item Variant Attribute":
				return [
					types.SimpleNamespace(parent=roll.name, attribute="Roll Width", attribute_value="24 in", idx=1),
					types.SimpleNamespace(parent=sheet.name, attribute="Sheet Size", attribute_value="13 × 19 in", idx=1),
				]
			return []

		frappe.get_all = get_all

		labels = module.get_inventory_labels("Stores - LPS")
		roll_item_label = next(label for label in labels if label["item_code"] == roll.name)
		sheet_item_label = next(label for label in labels if label["item_code"] == sheet.name)
		self.assertEqual(queried_doctypes, ["Item", "Item"])
		self.assertEqual(len(labels), 2)
		self.assertEqual(roll_item_label["tracking"], "Item")
		self.assertEqual(roll_item_label["label_code"], "LP000042")
		self.assertTrue(roll_item_label["has_internal_barcode"])
		self.assertEqual(roll_item_label["manufacturer"], "Hahnemühle")
		self.assertEqual(roll_item_label["paper_line"], "Torchon — 285 GSM")
		self.assertEqual(roll_item_label["form_size"], 'ROLL - 24"')
		self.assertEqual(sheet_item_label["label_code"], "INV000043")
		self.assertFalse(sheet_item_label["has_internal_barcode"])
		self.assertEqual(sheet_item_label["legacy_internal_barcode"], "INV000043")
		self.assertEqual(sheet_item_label["form_size"], 'SHEET - 13 × 19"')

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
		module._internal_barcodes_by_item = lambda _names: {roll.name: "LP000042"}
		module._next_internal_barcode = lambda: "LP000043"
		frappe.get_doc = lambda doctype, name: sheet_doc if (doctype, name) == ("Item", sheet.name) else None

		assignment = module.assign_missing_internal_barcodes("Stores - LPS", limit=1)
		self.assertEqual(assignment["created"], [{"item_code": sheet.name, "barcode": "LP000043"}])
		self.assertEqual(assignment["assigned"], 2)
		self.assertEqual(assignment["remaining"], 1)
		self.assertEqual(assignment["total"], 3)
		self.assertEqual(sheet_doc.checked_permission, "write")
		self.assertEqual(sheet_doc.appended_fieldname, "barcodes")
		self.assertEqual(sheet_doc.barcodes[0].barcode, "LP000043")
		self.assertTrue(sheet_doc.saved)

		legacy_doc = ItemDoc(roll.name)
		legacy_doc.barcodes = [
			types.SimpleNamespace(barcode="012345678905"),
			types.SimpleNamespace(barcode="INV000042"),
		]
		legacy_doc.remove = lambda row: legacy_doc.barcodes.remove(row)
		module._inventory_label_items = lambda: [roll]
		module._inventory_barcode_maps = lambda _names: ({}, {roll.name: "INV000042"})
		frappe.db = types.SimpleNamespace(get_value=lambda *_args, **_kwargs: None)
		frappe.get_doc = lambda doctype, name: legacy_doc if (doctype, name) == ("Item", roll.name) else None

		replacement = module.replace_legacy_internal_barcodes("Stores - LPS")
		self.assertEqual(
			replacement["replaced"],
			[{"item_code": roll.name, "from": "INV000042", "barcode": "LP000042"}],
		)
		self.assertEqual(replacement["remaining"], 0)
		self.assertEqual([row.barcode for row in legacy_doc.barcodes], ["012345678905", "LP000042"])
		self.assertEqual(NamingSeries.values["LP.######"], 42)

		class Row(dict):
			__getattr__ = dict.get

		purchase_item = types.SimpleNamespace(
			name=roll.name,
			stock_uom="Foot",
			uoms=[types.SimpleNamespace(uom="Roll 39.37 Foot", conversion_factor=39.37)],
			item_defaults=[
				types.SimpleNamespace(company="Lightpress Studios", default_supplier="B&H Photo Video")
			],
		)
		price_rows = [
			Row(
				name="PRICE-001",
				price_list="Standard Buying",
				price_list_rate=257.99,
				uom="Roll 39.37 Foot",
				supplier="B&H Photo Video",
				currency="USD",
				valid_from="2026-07-01",
				valid_upto=None,
				si_merchant_url="https://example.com/torchon",
				si_last_verified_on="2026-07-18",
			),
			Row(
				name="PRICE-EXPIRED",
				price_list="Standard Buying",
				price_list_rate=199,
				uom="Roll 39.37 Foot",
				supplier="B&H Photo Video",
				currency="USD",
				valid_from="2026-01-01",
				valid_upto="2026-06-30",
			),
		]
		frappe.get_cached_doc = lambda doctype: types.SimpleNamespace(
			paper_cost_price_list="Standard Buying"
		)
		frappe.get_list = lambda doctype, **_kwargs: price_rows if doctype == "Item Price" else []
		frappe.db = types.SimpleNamespace(
			has_column=lambda doctype, fieldname: (doctype, fieldname) == ("Item Price", "si_merchant_url"),
			exists=lambda doctype, filters: doctype == "Supplier" and filters["name"] == "B&H Photo Video",
		)
		module.nowdate = lambda: "2026-07-19"

		purchase_defaults = module._purchase_defaults(purchase_item, "Lightpress Studios")
		self.assertEqual(purchase_defaults["default_supplier"], "B&H Photo Video")
		self.assertEqual(purchase_defaults["buying_price_list"], "Standard Buying")
		self.assertEqual(len(purchase_defaults["buying_prices"]), 1)
		self.assertAlmostEqual(
			purchase_defaults["buying_prices"][0]["stock_rate"],
			257.99 / 39.37,
		)


if __name__ == "__main__":
	unittest.main()
