import unittest

from studio_inventory.hooks import standard_dropdown_items, website_route_rules


class WebsiteRouteTests(unittest.TestCase):
	def test_price_calculator_is_available_from_the_global_crm_menu(self):
		self.assertIn(
			{
				"name1": "studio_inventory_price_calculator",
				"label": "Price Calculator",
				"type": "Route",
				"route": "/studio-inventory?mode=price",
				"icon": "calculator",
				"open_in_new_window": 0,
				"is_standard": 0,
			},
			standard_dropdown_items,
		)

	def test_friendly_app_routes_resolve_to_native_page(self):
		self.assertIn(
			{"from_route": "/studio-inventory", "to_route": "studio_inventory"},
			website_route_rules,
		)
		self.assertIn(
			{
				"from_route": "/studio-inventory/<path:app_path>",
				"to_route": "studio_inventory",
			},
			website_route_rules,
		)


if __name__ == "__main__":
	unittest.main()
