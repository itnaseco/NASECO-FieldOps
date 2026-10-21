# Copyright (c) 2026, NASECO and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCropCycleStage(FrappeTestCase):
	def test_link_controls_use_stage_name_as_title(self):
		meta = frappe.get_meta("Crop Cycle Stage")

		self.assertEqual(meta.title_field, "stage_name")
		self.assertTrue(meta.show_title_field_in_link)
		self.assertIn("stage_name", meta.get_search_fields())
		self.assertIn("stage_code", meta.get_search_fields())
		self.assertIn("crop_cycle", meta.get_search_fields())
