import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from studio_inventory.domain import DomainError
from studio_inventory.pricing import PricingRules
from studio_inventory.pricing_model import validate_rule_definitions


class StudioPricingModel(Document):
	def validate(self):
		try:
			PricingRules.from_mapping(
				{
					name: self.get(name)
					for name in PricingRules.__dataclass_fields__
				}
			)
			validate_rule_definitions(self.rules)
		except DomainError as error:
			frappe.throw(_(str(error)), frappe.ValidationError)

		if self.effective_from and self.effective_to:
			if getdate(self.effective_from) > getdate(self.effective_to):
				frappe.throw(_("Effective From cannot be after Effective To."), frappe.ValidationError)

		if self.disabled and frappe.db.get_single_value(
			"Studio Pricing Settings", "active_pricing_model"
		) == self.name:
			frappe.throw(_("The active pricing model cannot be disabled."), frappe.ValidationError)

	def before_save(self):
		self.model_revision = 1 if self.is_new() else cint(self.model_revision) + 1
