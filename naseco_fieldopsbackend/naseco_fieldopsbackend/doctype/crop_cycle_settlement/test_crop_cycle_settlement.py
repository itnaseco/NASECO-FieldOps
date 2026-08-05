from types import SimpleNamespace
from unittest import TestCase

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_settlement.crop_cycle_settlement import (
	CropCycleSettlement,
)


class TestCropCycleSettlement(TestCase):
	def test_balances_stock_recovery_then_supplier_advances(self):
		settlement = self.make_settlement(
			harvest=10_000_000,
			stock_recovery=2_000_000,
			cash_advance=3_000_000,
			additions=500_000,
			deductions=250_000,
		)

		CropCycleSettlement.calculate_totals(settlement)

		self.assertEqual(settlement.invoice_total, 8_250_000)
		self.assertEqual(settlement.cash_advance_to_allocate, 3_000_000)
		self.assertEqual(settlement.net_payable, 5_250_000)
		self.assertEqual(settlement.unrecovered_balance, 0)
		self.assertEqual(settlement.status, "Prepared")

	def test_carries_forward_exposure_above_harvest_value(self):
		settlement = self.make_settlement(
			harvest=2_000_000,
			stock_recovery=3_000_000,
			cash_advance=1_000_000,
		)

		CropCycleSettlement.calculate_totals(settlement)

		self.assertEqual(settlement.stock_recovery_to_deduct, 2_000_000)
		self.assertEqual(settlement.stock_recovery_shortfall, 1_000_000)
		self.assertEqual(settlement.cash_advance_to_allocate, 0)
		self.assertEqual(settlement.cash_advance_shortfall, 1_000_000)
		self.assertEqual(settlement.net_payable, 0)
		self.assertEqual(settlement.unrecovered_balance, 2_000_000)

	@staticmethod
	def make_settlement(
		harvest,
		stock_recovery,
		cash_advance,
		additions=0,
		deductions=0,
	):
		adjustments = []
		if additions:
			adjustments.append(SimpleNamespace(add_or_deduct="Add", amount=additions))
		if deductions:
			adjustments.append(SimpleNamespace(add_or_deduct="Deduct", amount=deductions))
		return SimpleNamespace(
			harvest_receipts=[SimpleNamespace(amount=harvest)],
			pricing_lines=[],
			stock_inputs=[SimpleNamespace(recoverable_amount=stock_recovery)],
			cash_advances=[SimpleNamespace(available_amount=cash_advance)],
			adjustments=adjustments,
			status="Draft",
		)
