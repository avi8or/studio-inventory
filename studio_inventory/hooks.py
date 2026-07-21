app_name = "studio_inventory"
app_title = "Studio Inventory"
app_publisher = "Tyler Miller"
app_description = "Studio inventory and print-pricing workflows backed by native ERPNext records"
app_email = ""
app_license = "MIT"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "studio_inventory",
		"logo": "/assets/studio_inventory/images/package-open.svg",
		"title": "Studio Inventory",
		"route": "/studio-inventory",
		"has_permission": "studio_inventory.permissions.check_app_permission",
	}
]

standard_dropdown_items = [
	{
		"name1": "studio_inventory_price_calculator",
		"label": "Price Calculator",
		"type": "Route",
		"route": "/studio-inventory?mode=price",
		"icon": "calculator",
		"open_in_new_window": 0,
		"is_standard": 1,
	}
]

website_route_rules = [
	{"from_route": "/studio-inventory", "to_route": "studio_inventory"},
	{"from_route": "/studio-inventory/<path:app_path>", "to_route": "studio_inventory"},
]

export_python_type_annotations = True
require_type_annotated_api_methods = True

after_install = "studio_inventory.setup.install"
after_migrate = "studio_inventory.setup.after_migrate"

doctype_js = {
	"Quotation": "public/js/quotation.js",
	"Sales Order": "public/js/sales_order.js",
}

doc_events = {
	"Quotation": {
		"validate": "studio_inventory.pricing_api.validate_quotation",
	},
	"Sales Order": {
		"before_validate": "studio_inventory.crm_bridge.ensure_customer_from_quotation",
	},
}
