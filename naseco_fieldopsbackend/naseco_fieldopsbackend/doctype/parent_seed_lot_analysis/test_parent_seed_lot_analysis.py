from unittest import TestCase

from naseco_fieldopsbackend.parent_seed_calculation import calculate_parent_requirement


class TestParentSeedCalculation(TestCase):
	def test_ratio_germination_and_kernel_weight_calculation(self):
		male = calculate_parent_requirement(
			total_plants_per_hectare=50000,
			parent_ratio=1,
			total_ratio=5,
			germination_percent=90,
			thousand_kernel_weight_g=300,
			area_hectares=2.5,
		)
		self.assertEqual(str(male["expected_plants_per_hectare"]), "10000.000000")
		self.assertEqual(str(male["planned_kg_per_hectare"]), "3.333333")
		self.assertEqual(str(male["planned_quantity_kg"]), "8.333333")

	def test_allowance_is_separate_from_germination(self):
		result = calculate_parent_requirement(
			total_plants_per_hectare=50000,
			parent_ratio=4,
			total_ratio=5,
			germination_percent=85,
			thousand_kernel_weight_g=280,
			allowance_percent=5,
		)
		self.assertEqual(str(result["population_percent"]), "80.000000")
		self.assertEqual(str(result["planned_kg_per_hectare"]), "13.835294")

	def test_invalid_germination_is_rejected(self):
		with self.assertRaisesRegex(ValueError, "Germination"):
			calculate_parent_requirement(
				total_plants_per_hectare=50000,
				parent_ratio=1,
				total_ratio=5,
				germination_percent=0,
				thousand_kernel_weight_g=300,
			)
