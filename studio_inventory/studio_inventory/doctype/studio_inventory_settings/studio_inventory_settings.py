from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document


class StudioInventorySettings(Document):
	def validate(self) -> None:
		self.internal_barcode_prefix = (self.internal_barcode_prefix or "SI").strip().upper()
		if not re.fullmatch(r"[A-Z]{2,6}", self.internal_barcode_prefix):
			frappe.throw(
				_("Internal Barcode Prefix must contain 2–6 letters."),
				frappe.ValidationError,
			)
