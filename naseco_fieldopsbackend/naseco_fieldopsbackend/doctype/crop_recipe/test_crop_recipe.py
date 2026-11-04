# Copyright (c) 2026, Naseco and Contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase

import frappe

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe import (
	get_parent_seed_input_hash,
	get_parent_seed_population,
	get_stage_day_number,
	select_parent_seed_item_mapping,
)


class TestCropRecipe(TestCase):
	def test_stage_day_number_uses_stage_end_milestone(self):
		self.assertEqual(get_stage_day_number(0, 0), "1")
		self.assertEqual(get_stage_day_number(7, 14), "14")
		self.assertEqual(get_stage_day_number(150, 180), "180")

	def test_stage_day_number_describes_pre_planting_windows(self):
		self.assertEqual(get_stage_day_number(-30, -1), "30 Days Prior")
		self.assertEqual(get_stage_day_number(-1, -1), "1 Day Prior")

	def test_stage_day_number_rejects_incomplete_or_invalid_windows(self):
		self.assertIsNone(get_stage_day_number(None, 14))
		self.assertIsNone(get_stage_day_number(14, None))
		self.assertIsNone(get_stage_day_number(15, 14))

	def test_parent_seed_population_prefers_variety_override(self):
		recipe = SimpleNamespace(
			expected_plants_per_hectare=50000,
			applicable_varieties=[SimpleNamespace(
				enabled=1,
				variety="Bazooka",
				expected_plants_per_hectare_override=52000,
			)],
		)

		self.assertEqual(get_parent_seed_population(recipe, "Bazooka"), 52000)
		self.assertEqual(get_parent_seed_population(recipe, "Other"), 50000)

	def test_parent_seed_input_hash_changes_when_assumptions_change(self):
		row = frappe._dict(
			variety="Bazooka", parentage="Bazooka Parents", parent_role="Female",
			parent_variety="B53", required_seed_category="Basic",
			required_seed_class="Basic", ratio_value=4,
			calculation_basis="Assumed Values", lot_analysis=None,
			item_code="B53-BASIC", germination_percent=90,
			thousand_kernel_weight_g=300, assumption_source="Breeder declaration",
			assumption_reason="Pre-season planning", recovery_policy="Fully Recoverable",
			recoverable_percent=100, source_warehouse="Seed Stores",
		)
		recipe = frappe._dict(
			variety_scope="Specific Varieties", expected_plants_per_hectare=50000,
			seed_requirement_allowance_percent=5,
			applicable_varieties=[frappe._dict(
				variety="Bazooka", enabled=1, expected_plants_per_hectare_override=0,
			)],
			parent_seed_items=[row],
		)

		original = get_parent_seed_input_hash(recipe)
		row.germination_percent = 91
		self.assertNotEqual(original, get_parent_seed_input_hash(recipe))

	def test_parent_seed_item_mapping_prefers_unique_default(self):
		item, source = select_parent_seed_item_mapping([
			{"item_code": "B53-OLD", "is_default": 0},
			{"item_code": "B53-DEFAULT", "is_default": 1},
		])
		self.assertEqual(item, "B53-DEFAULT")
		self.assertEqual(source, "Default Crop Variety Mapping")

	def test_parent_seed_item_mapping_autofills_unique_mapping(self):
		item, source = select_parent_seed_item_mapping([
			{"item_code": "Z36-BASIC", "is_default": 0},
		])
		self.assertEqual(item, "Z36-BASIC")
		self.assertEqual(source, "Unique Crop Variety Mapping")

	def test_parent_seed_item_mapping_requires_choice_when_ambiguous(self):
		item, source = select_parent_seed_item_mapping([
			{"item_code": "Z36-A", "is_default": 0},
			{"item_code": "Z36-B", "is_default": 0},
		])
		self.assertIsNone(item)
		self.assertEqual(source, "Selection Required")
