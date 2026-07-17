import unittest

from studio_inventory.hooks import website_route_rules


class WebsiteRouteTests(unittest.TestCase):
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
