import frappe
from frappe import _
from frappe.model.document import Document

from studio_inventory.domain import DomainError
from studio_inventory.pricing import PricingRules


class StudioPricingSettings(Document):
	def validate(self):
		try:
			PricingRules.from_mapping(
				{
					name: self.get(name)
					for name in PricingRules.__dataclass_fields__
				}
			)
		except DomainError as error:
			frappe.throw(_(str(error)), frappe.ValidationError)

		if self.default_print_item:
			item = frappe.db.get_value(
				"Item",
				self.default_print_item,
				["disabled", "is_sales_item", "has_variants"],
				as_dict=True,
			)
			if not item or item.disabled or not item.is_sales_item or item.has_variants:
				frappe.throw(_("Default Print Item must be active, sellable, and without variants."))

		if self.paper_cost_price_list and not frappe.db.get_value(
			"Price List", self.paper_cost_price_list, "buying"
		):
			frappe.throw(_("Paper Cost Price List must be a Buying Price List."))
