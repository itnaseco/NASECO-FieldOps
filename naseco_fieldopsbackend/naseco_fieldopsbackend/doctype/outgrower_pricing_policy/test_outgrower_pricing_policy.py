from types import SimpleNamespace
from unittest import TestCase

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_pricing_policy.outgrower_pricing_policy import (
	calculate_harvest_pricing,
)


class TestOutgrowerPricingPolicy(TestCase):
	def test_applies_highest_26b_band_and_excess_rate(self):
		result = calculate_harvest_pricing(
			self.policy(),
			net_dry_qty=1200,
			eligible_area_hectares=1,
			genetic_purity_percent=98,
			germination_percent=97,
		)

		self.assertEqual(result.pricing_band, "1000+; 98%+")
		self.assertEqual(result.base_quota_qty, 1000)
		self.assertEqual(result.excess_qty, 200)
		self.assertEqual(result.gross_value, 2_420_000)
		self.assertEqual(result.potential_bonus_amount, 120_000)

	def test_low_germination_forces_grain_price(self):
		result = calculate_harvest_pricing(
			self.policy(),
			net_dry_qty=1000,
			eligible_area_hectares=1,
			genetic_purity_percent=99,
			germination_percent=94,
		)

		self.assertEqual(result.price_basis, "Grain Price")
		self.assertEqual(result.gross_value, 1_200_000)
		self.assertEqual(result.potential_bonus_amount, 0)

	def test_applies_screen_and_reject_deductions(self):
		result = calculate_harvest_pricing(
			self.policy(),
			net_dry_qty=1000,
			eligible_area_hectares=1,
			genetic_purity_percent=96,
			germination_percent=96,
			undersize_percent=6,
			reject_percent=2,
		)

		self.assertEqual(result.gross_value, 2_000_000)
		self.assertEqual(result.screen_deduction, 100_000)
		self.assertEqual(result.reject_deduction, 100_000)
		self.assertEqual(result.initial_payable_value, 1_800_000)

	@staticmethod
	def policy():
		return SimpleNamespace(
			pricing_bands=[
				SimpleNamespace(
					band_name="1000+; 98%+",
					minimum_yield_kg_per_hectare=1000,
					maximum_yield_kg_per_hectare=0,
					minimum_purity_percent=98,
					maximum_purity_percent=0,
					price_basis="Fixed Rate",
					rate_per_kg=2100,
				),
				SimpleNamespace(
					band_name="1000+; 95-98%",
					minimum_yield_kg_per_hectare=1000,
					maximum_yield_kg_per_hectare=0,
					minimum_purity_percent=95,
					maximum_purity_percent=98,
					price_basis="Fixed Rate",
					rate_per_kg=2000,
				),
			],
			minimum_germination_percent=95,
			quota_kg_per_hectare=1000,
			excess_rate_per_kg=1600,
			grain_rate_per_kg=1200,
			undersize_threshold_percent=5,
			screen_weight_deduction_percent=5,
			reject_threshold_percent=1,
			reject_value_deduction_percent=5,
			high_bonus_purity_threshold=95,
			high_bonus_rate_per_kg=100,
			standard_bonus_purity_threshold=85,
			standard_bonus_rate_per_kg=50,
		)
