import unittest

from studio_inventory.domain import DomainError
from studio_inventory.pricing import (
	PaperDimensions,
	PricingRules,
	calculate_print,
	consumed_paper_cost,
	cost_per_sq_in,
	estimate_consumption,
	parse_paper_dimensions,
)


class DimensionAndCostTests(unittest.TestCase):
	def test_sheet_dimensions_parse_inches(self):
		dimensions = parse_paper_dimensions(stock_uom="Sheet", attribute_value="13 × 19 in")

		self.assertEqual(dimensions.width_in, 13)
		self.assertEqual(dimensions.height_in, 19)

	def test_metric_sheet_dimensions_convert_to_inches(self):
		dimensions = parse_paper_dimensions(stock_uom="Sheet", attribute_value="210 × 297 mm")

		self.assertAlmostEqual(dimensions.width_in, 8.2677165)
		self.assertAlmostEqual(dimensions.height_in, 11.6929134)

	def test_roll_width_parses_variant_attribute(self):
		dimensions = parse_paper_dimensions(stock_uom="Foot", attribute_value="24 in width")

		self.assertEqual(dimensions.width_in, 24)
		self.assertIsNone(dimensions.height_in)

	def test_pack_item_price_normalizes_to_cost_per_square_inch(self):
		dimensions = PaperDimensions(stock_uom="Sheet", width_in=17, height_in=22)

		cost = cost_per_sq_in(price=135.58, conversion_factor=25, dimensions=dimensions)

		self.assertAlmostEqual(cost, 0.0145, places=4)

	def test_roll_item_price_normalizes_through_purchase_uom(self):
		dimensions = PaperDimensions(stock_uom="Foot", width_in=24)

		cost = cost_per_sq_in(price=100, conversion_factor=50, dimensions=dimensions)

		self.assertAlmostEqual(cost, 100 / 50 / (24 * 12))


class PricingTests(unittest.TestCase):
	def test_approved_price_table_matches_existing_calculator(self):
		fixtures = [
			(4, 6, 0, 5),
			(5, 7, 0, 6),
			(8, 10, 0, 11),
			(11, 14, 0, 19),
			(12, 18, 0, 26),
			(16, 20, 0, 38),
			(16, 20, 2, 40),
			(16, 24, 0, 44),
			(20, 24, 0, 53),
			(24, 36, 0, 89),
			(30, 40, 0, 120),
		]
		for width, height, border, expected in fixtures:
			with self.subTest(width=width, height=height, border=border):
				result = calculate_print(
					artwork_width_in=width,
					artwork_height_in=height,
					border_in=border,
					quantity=1,
					time_minutes=0,
					ink_cost_per_sq_in=0.012,
					paper_cost_per_sq_in=0.0070625,
				)

				self.assertEqual(result.list_unit_price, expected)

	def test_locked_multi_quantity_cost_and_margin_fixture(self):
		result = calculate_print(
			artwork_width_in=16,
			artwork_height_in=20,
			border_in=2,
			quantity=10,
			time_minutes=30,
			ink_cost_per_sq_in=0.012,
			paper_cost_per_sq_in=0.0070625,
		)

		self.assertEqual(result.list_unit_price, 40)
		self.assertEqual(result.line_total, 400)
		self.assertAlmostEqual(result.paper_cost, 33.9)
		self.assertAlmostEqual(result.ink_cost, 38.4)
		self.assertAlmostEqual(result.time_cost, 37.5)
		self.assertAlmostEqual(result.gross_profit, 290.2)
		self.assertAlmostEqual(result.gross_margin_pct, 72.55)

	def test_production_time_affects_margin_not_selling_price(self):
		inputs = {
			"artwork_width_in": 16,
			"artwork_height_in": 20,
			"border_in": 2,
			"quantity": 10,
			"ink_cost_per_sq_in": 0.012,
			"paper_cost_per_sq_in": 0.0070625,
		}

		with_time = calculate_print(**inputs, time_minutes=30)
		without_time = calculate_print(**inputs, time_minutes=0)

		self.assertEqual(with_time.line_total, without_time.line_total)
		self.assertLess(with_time.gross_margin_pct, without_time.gross_margin_pct)

	def test_actual_stock_waste_reduces_margin_without_changing_base_price(self):
		inputs = {
			"artwork_width_in": 16,
			"artwork_height_in": 20,
			"border_in": 2,
			"quantity": 1,
			"time_minutes": 0,
			"ink_cost_per_sq_in": 0.012,
			"paper_cost_per_sq_in": 0.0070625,
		}

		narrow_roll = calculate_print(**inputs, actual_paper_cost=4)
		wide_roll = calculate_print(**inputs, actual_paper_cost=8)

		self.assertEqual(narrow_roll.list_unit_price, wide_roll.list_unit_price)
		self.assertEqual(narrow_roll.paper_cost, 4)
		self.assertEqual(wide_roll.paper_cost, 8)
		self.assertLess(wide_roll.gross_margin_pct, narrow_roll.gross_margin_pct)

	def test_settings_with_blank_values_use_defaults(self):
		rules = PricingRules.from_mapping({"hourly_rate": None, "material_markup": ""})

		self.assertEqual(rules.hourly_rate, 75)
		self.assertEqual(rules.material_markup, 2)


class ConsumptionTests(unittest.TestCase):
	def test_wider_roll_values_the_unused_width_as_internal_cost(self):
		finished = {"finished_width_in": 20, "finished_height_in": 24, "quantity": 1}
		narrow_dimensions = PaperDimensions(stock_uom="Foot", width_in=24)
		wide_dimensions = PaperDimensions(stock_uom="Foot", width_in=44)
		narrow_consumption = estimate_consumption(dimensions=narrow_dimensions, **finished)
		wide_consumption = estimate_consumption(dimensions=wide_dimensions, **finished)

		narrow_cost = consumed_paper_cost(
			dimensions=narrow_dimensions,
			consumption_quantity=narrow_consumption.quantity,
			paper_cost_per_sq_in=0.01,
		)
		wide_cost = consumed_paper_cost(
			dimensions=wide_dimensions,
			consumption_quantity=wide_consumption.quantity,
			paper_cost_per_sq_in=0.01,
		)

		self.assertEqual(narrow_consumption.quantity, wide_consumption.quantity)
		self.assertGreater(wide_cost, narrow_cost)

	def test_sheet_layout_uses_physical_grid(self):
		estimate = estimate_consumption(
			dimensions=PaperDimensions(stock_uom="Sheet", width_in=17, height_in=22),
			finished_width_in=8,
			finished_height_in=10,
			quantity=50,
		)

		self.assertEqual(estimate.prints_per_sheet, 4)
		self.assertEqual(estimate.quantity, 13)

	def test_roll_layout_can_place_multiple_prints_across(self):
		estimate = estimate_consumption(
			dimensions=PaperDimensions(stock_uom="Foot", width_in=24),
			finished_width_in=8,
			finished_height_in=10,
			quantity=6,
		)

		self.assertEqual(estimate.quantity, 2)
		self.assertEqual(estimate.prints_across, 3)

	def test_roll_length_rounds_to_configured_increment(self):
		estimate = estimate_consumption(
			dimensions=PaperDimensions(stock_uom="Foot", width_in=24),
			finished_width_in=20,
			finished_height_in=30,
			quantity=5,
			roll_increment_ft=1,
		)

		self.assertEqual(estimate.quantity, 13)
		self.assertEqual(estimate.orientation, "width-across")

	def test_no_fit_is_rejected_before_quoting(self):
		with self.assertRaisesRegex(DomainError, "wider than"):
			estimate_consumption(
				dimensions=PaperDimensions(stock_uom="Foot", width_in=24),
				finished_width_in=30,
				finished_height_in=40,
				quantity=1,
			)


if __name__ == "__main__":
	unittest.main()
