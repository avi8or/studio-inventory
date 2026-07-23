import json
import unittest
from pathlib import Path

from studio_inventory.domain import DomainError
from studio_inventory.pricing import PricingRules, calculate_print
from studio_inventory.pricing_model import (
	PricingRuleContext,
	resolve_pricing_model,
	validate_rule_definitions,
)


class PricingModelResolutionTests(unittest.TestCase):
	def context(self, **overrides):
		values = {
			"paper_item": "PAPER-TORCHON-24",
			"paper_brand": "Hahnemuhle",
			"stock_uom": "Foot",
			"artwork_width_in": 8,
			"artwork_height_in": 10,
			"paper_cost_per_sq_in": 0.15,
			"quantity": 1,
		}
		values.update(overrides)
		return PricingRuleContext(**values)

	def test_no_rules_preserves_the_existing_price(self):
		resolution = resolve_pricing_model(PricingRules(), [], self.context())

		result = calculate_print(
			artwork_width_in=8,
			artwork_height_in=10,
			border_in=0,
			quantity=1,
			time_minutes=0,
			ink_cost_per_sq_in=resolution.rules.ink_cost_per_sq_in,
			paper_cost_per_sq_in=0.0070625,
			rules=resolution.rules,
			price_adjustments=resolution.price_adjustments,
		)

		self.assertEqual(result.list_unit_price, 11)
		self.assertEqual(resolution.matched_rules, ())

	def test_exact_paper_and_size_can_set_a_minimum_price(self):
		rules = [
			{
				"enabled": 1,
				"rule_name": "Torchon small-print floor",
				"priority": 10,
				"paper_item": "PAPER-TORCHON-24",
				"exact_width_in": 8,
				"exact_height_in": 10,
				"target": "Minimum Unit Price",
				"operation": "Set",
				"value": 20,
			}
		]

		resolution = resolve_pricing_model(PricingRules(), rules, self.context())
		result = calculate_print(
			artwork_width_in=8,
			artwork_height_in=10,
			border_in=0,
			quantity=1,
			time_minutes=0,
			ink_cost_per_sq_in=resolution.rules.ink_cost_per_sq_in,
			paper_cost_per_sq_in=0.0070625,
			rules=resolution.rules,
			price_adjustments=resolution.price_adjustments,
		)

		self.assertEqual(result.list_unit_price, 20)
		self.assertEqual(resolution.matched_rules[0]["rule_name"], "Torchon small-print floor")

	def test_exact_size_is_orientation_independent(self):
		rules = [
			{
				"enabled": 1,
				"rule_name": "Eight by ten",
				"priority": 10,
				"exact_width_in": 8,
				"exact_height_in": 10,
				"target": "Minimum Unit Price",
				"operation": "Set",
				"value": 20,
			}
		]

		resolution = resolve_pricing_model(
			PricingRules(),
			rules,
			self.context(artwork_width_in=10, artwork_height_in=8),
		)

		self.assertEqual(len(resolution.price_adjustments), 1)

	def test_cost_band_can_change_only_material_markup(self):
		rules = [
			{
				"enabled": 1,
				"rule_name": "Premium paper cost response",
				"priority": 20,
				"min_paper_cost_per_sq_in": 0.14,
				"max_paper_cost_per_sq_in": 0.25,
				"target": "Material Markup Multiplier",
				"operation": "Multiply",
				"value": 1.25,
			}
		]

		resolution = resolve_pricing_model(PricingRules(), rules, self.context())

		self.assertEqual(resolution.rules.material_markup, 2.5)
		self.assertEqual(resolution.rules.production_base, PricingRules().production_base)

	def test_nonmatching_rule_does_not_change_the_model(self):
		rules = [
			{
				"enabled": 1,
				"rule_name": "Other paper only",
				"priority": 10,
				"paper_item": "PAPER-OTHER",
				"target": "Minimum Unit Price",
				"operation": "Set",
				"value": 99,
			}
		]

		resolution = resolve_pricing_model(PricingRules(), rules, self.context())

		self.assertEqual(resolution.rules, PricingRules())
		self.assertEqual(resolution.price_adjustments, ())

	def test_conditional_minimum_margin_can_raise_a_high_cost_print(self):
		rules = [
			{
				"enabled": 1,
				"rule_name": "Premium paper margin floor",
				"priority": 10,
				"min_paper_cost_per_sq_in": 0.14,
				"target": "Minimum Pricing Margin",
				"operation": "Set",
				"value": 60,
			}
		]
		resolution = resolve_pricing_model(PricingRules(), rules, self.context())

		result = calculate_print(
			artwork_width_in=8,
			artwork_height_in=10,
			border_in=0,
			quantity=1,
			time_minutes=0,
			ink_cost_per_sq_in=resolution.rules.ink_cost_per_sq_in,
			paper_cost_per_sq_in=0.15,
			rules=resolution.rules,
			price_adjustments=resolution.price_adjustments,
			actual_paper_cost=12,
		)

		self.assertGreaterEqual(result.gross_margin_pct, 60)
		self.assertGreater(result.margin_floor_unit_price, 0)


class PricingModelValidationTests(unittest.TestCase):
	def test_exact_size_requires_both_dimensions(self):
		with self.assertRaisesRegex(DomainError, "both width and height"):
			validate_rule_definitions(
				[
					{
						"enabled": 1,
						"rule_name": "Incomplete size",
						"priority": 10,
						"exact_width_in": 8,
						"target": "Minimum Unit Price",
						"operation": "Set",
						"value": 20,
					}
				]
			)

	def test_overlapping_rules_with_duplicate_priority_and_target_are_rejected(self):
		rules = [
			{
				"enabled": 1,
				"rule_name": "First",
				"priority": 10,
				"target": "Minimum Unit Price",
				"operation": "Set",
				"value": 20,
			},
			{
				"enabled": 1,
				"rule_name": "Second",
				"priority": 10,
				"target": "Minimum Unit Price",
				"operation": "Add",
				"value": 2,
			},
		]

		with self.assertRaisesRegex(DomainError, "same priority and target"):
			resolve_pricing_model(PricingRules(), rules, PricingModelResolutionTests().context())


class PricingModelSchemaTests(unittest.TestCase):
	def test_model_and_child_rule_doctypes_are_native_frappe_records(self):
		root = Path(__file__).parents[1] / "studio_inventory" / "studio_inventory" / "doctype"
		model = json.loads(
			(root / "studio_pricing_model" / "studio_pricing_model.json").read_text()
		)
		rule = json.loads(
			(root / "studio_pricing_rule" / "studio_pricing_rule.json").read_text()
		)

		self.assertEqual(model["name"], "Studio Pricing Model")
		self.assertEqual(model["track_changes"], 1)
		self.assertIn(
			{
				"fieldname": "rules",
				"fieldtype": "Table",
				"label": "Rules and Overrides",
				"options": "Studio Pricing Rule",
			},
			model["fields"],
		)
		self.assertEqual(rule["name"], "Studio Pricing Rule")
		self.assertEqual(rule["istable"], 1)

	def test_business_terms_are_packaged_without_renaming_native_doctypes(self):
		translations = (
			Path(__file__).parents[1]
			/ "studio_inventory"
			/ "translations"
			/ "en.csv"
		).read_text()

		self.assertIn('"Lead","Inquiry"', translations)
		self.assertIn('"Deal","Estimate Request"', translations)
		self.assertIn('"Quotation","Estimate"', translations)
		self.assertIn('"Sales Order","Client Order"', translations)


if __name__ == "__main__":
	unittest.main()
