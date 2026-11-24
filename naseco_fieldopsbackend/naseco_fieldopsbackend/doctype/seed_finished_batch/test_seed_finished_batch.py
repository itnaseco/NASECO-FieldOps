from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase


class TestSeedFinishedBatch(UnitTestCase):
	def test_batch_item_must_match(self):
		doc = frappe.get_doc({
			"doctype": "Seed Finished Batch",
			"processing_handoff": "SPH-TEST",
			"harvest_lot": "SFHL-TEST",
			"item_code": "ITEM-A",
			"batch_no": "BATCH-B",
			"received_qty_kg": 10,
		})
		with patch("frappe.db.get_value", return_value="ITEM-B"):
			with self.assertRaises(frappe.ValidationError):
				doc.validate()

	def test_handoff_harvest_lot_must_match(self):
		doc = frappe.get_doc({
			"doctype": "Seed Finished Batch",
			"processing_handoff": "SPH-TEST",
			"harvest_lot": "SFHL-OTHER",
			"item_code": "ITEM-A",
			"batch_no": "BATCH-A",
			"received_qty_kg": 10,
		})
		with patch("frappe.db.get_value", return_value=frappe._dict(harvest_lot="SFHL-TEST", dispatch_date="2026-01-01")):
			with self.assertRaises(frappe.ValidationError):
				doc.before_validate()
