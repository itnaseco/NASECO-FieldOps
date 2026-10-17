from unittest import TestCase

from naseco_fieldopsbackend import api


class TestCropCyclePlannedInputMobile(TestCase):
	def test_crop_cycle_exports_plot_specific_planned_parent_seed_inputs(self):
		mobile = api._map_doc_to_mobile("Crop Cycle", {
			"doctype": "Crop Cycle",
			"name": "CC-001",
			"crop_cycle_id": "CC-001",
			"planned_inputs": [{
				"doctype": "Crop Cycle Planned Input",
				"name": "PLAN-1",
				"stage_name": "Planting",
				"item_code": "FEMALE-PARENT",
				"quantity_per_hectare": 18.5,
				"planned_qty": 7.4,
				"uom": "Kg",
				"required_by": "2026-10-20",
			}],
		})

		self.assertEqual(len(mobile["plannedInputs"]), 1)
		row = mobile["plannedInputs"][0]
		self.assertEqual(row["stageName"], "Planting")
		self.assertEqual(row["itemCode"], "FEMALE-PARENT")
		self.assertEqual(row["plannedQuantity"], 7.4)
		self.assertEqual(row["quantityPerHectare"], 18.5)
