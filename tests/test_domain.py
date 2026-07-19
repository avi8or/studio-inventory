import unittest

from studio_inventory.domain import DomainError, calculate_consumption, calculate_reconciliation, plan_receipt


class ReceiptPlanTests(unittest.TestCase):
	def test_sheet_pack_converts_to_stock_quantity(self):
		plan = plan_receipt(
			purchase_units=2,
			conversion_factor=25,
			unit_cost=87.50,
			purchase_uom="Pack 25 Sheet",
			batched=False,
		)

		self.assertEqual(plan.stock_quantity, 50)
		self.assertEqual(plan.physical_units, 2)
		self.assertIsNone(plan.quantity_per_batch)
		self.assertEqual(plan.stock_rate, 3.5)

	def test_roll_converts_purchase_units_to_aggregate_feet(self):
		plan = plan_receipt(
			purchase_units=2,
			conversion_factor=39.37,
			unit_cost=200,
			purchase_uom="Roll 39.37 Foot",
			batched=False,
		)

		self.assertEqual(plan.stock_quantity, 78.74)
		self.assertEqual(plan.physical_units, 2)
		self.assertIsNone(plan.quantity_per_batch)
		self.assertAlmostEqual(plan.stock_rate, 200 / 39.37)

	def test_single_roll_creates_one_batch(self):
		plan = plan_receipt(
			purchase_units=2,
			conversion_factor=50,
			unit_cost=200,
			purchase_uom="Roll 50 Foot",
			batched=True,
		)

		self.assertEqual(plan.stock_quantity, 100)
		self.assertEqual(plan.physical_units, 2)
		self.assertEqual(plan.quantity_per_batch, 50)

	def test_case_creates_one_batch_per_physical_roll(self):
		plan = plan_receipt(
			purchase_units=3,
			conversion_factor=100,
			unit_cost=360,
			purchase_uom="Case 2 × 50 Foot Rolls",
			batched=True,
		)

		self.assertEqual(plan.stock_quantity, 300)
		self.assertEqual(plan.physical_units, 6)
		self.assertEqual(plan.quantity_per_batch, 50)

	def test_batched_item_rejects_loose_stock_uom(self):
		with self.assertRaisesRegex(DomainError, "Roll or Case"):
			plan_receipt(
				purchase_units=1,
				conversion_factor=1,
				unit_cost=5,
				purchase_uom="Foot",
				batched=True,
			)


class QuantityChangeTests(unittest.TestCase):
	def test_explicit_ending_balance_computes_consumption(self):
		change = calculate_consumption(current=37.5, mode="ending", value=29.75)

		self.assertEqual(change.before, 37.5)
		self.assertEqual(change.change, -7.75)
		self.assertEqual(change.after, 29.75)

	def test_amount_cannot_exceed_current_balance(self):
		with self.assertRaisesRegex(DomainError, "cannot exceed"):
			calculate_consumption(current=10, mode="amount", value=11)

	def test_reconciliation_records_signed_delta(self):
		change = calculate_reconciliation(current=37.5, actual=33)

		self.assertEqual(change.change, -4.5)
		self.assertEqual(change.after, 33)

	def test_reconciliation_rejects_noop(self):
		with self.assertRaisesRegex(DomainError, "already matches"):
			calculate_reconciliation(current=10, actual=10)


if __name__ == "__main__":
	unittest.main()
