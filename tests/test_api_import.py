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


if __name__ == "__main__":
	unittest.main()
