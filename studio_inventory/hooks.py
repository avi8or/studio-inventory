app_name = "studio_inventory"
app_title = "Studio Inventory"
app_publisher = "Tyler Miller"
app_description = "Scanner-first inventory workflows backed by native ERPNext transactions"
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

website_route_rules = [
	{"from_route": "/studio-inventory/<path:app_path>", "to_route": "studio_inventory"},
]

export_python_type_annotations = True
require_type_annotated_api_methods = True
