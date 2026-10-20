# Copyright (c) 2026, Naseco and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe import (
	get_stage_day_number,
)


class TestCropRecipe(FrappeTestCase):
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
