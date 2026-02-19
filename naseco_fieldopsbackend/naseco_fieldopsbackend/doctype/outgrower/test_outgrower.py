# Copyright (c) 2026, Naseco and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from naseco_fieldopsbackend import api


class TestOutgrower(FrappeTestCase):
	def test_push_pull_outgrower_bank_fields(self):
		outgrower_name = f"OG-SYNC-{frappe.generate_hash(length=8)}"
		try:
			push_payload = {
				"data": [
					{
						"storeName": "outgrowers",
						"recordId": outgrower_name,
						"operation": "SYNC",
						"payload": {
							"outgrowerId": outgrower_name,
							"fullName": "Sync Test Farmer",
							"registrationDate": "2026-02-01",
							"bankAccount": "ACC-123",
							"outgrowerType": "Individual",
						},
					}
				]
			}
			result = api.push_sync_data(push_payload)
			self.assertTrue(result.get("success"))

			doc = frappe.get_doc("Outgrower", outgrower_name)
			self.assertEqual(doc.bank_account, "ACC-123")
			self.assertEqual(doc.outgrower_type, "Individual")

			legacy_update = [
				{
					"doctype": "Outgrower",
					"operation": "UPDATE",
					"doc": {
						"doctype": "Outgrower",
						"name": outgrower_name,
						"bank_account": "ACC-999",
						"outgrower_type": "Company",
					},
				}
			]
			update_result = api.bulk_sync(legacy_update)
			self.assertTrue(update_result.get("success"))

			doc.reload()
			self.assertEqual(doc.bank_account, "ACC-999")
			self.assertEqual(doc.outgrower_type, "Company")

			modified = api.get_modified_records(
				doctype="Outgrower",
				since="2000-01-01T00:00:00Z",
			)
			modified_records = modified.get("modified_records", {}).get("Outgrower", [])
			self.assertTrue(modified_records)
			out_doc = [d for d in modified_records if d.get("name") == outgrower_name][0]
			self.assertEqual(out_doc.get("bank_account"), "ACC-999")
			self.assertEqual(out_doc.get("outgrower_type"), "Company")
			self.assertEqual(out_doc.get("bankAccount"), "ACC-999")
			self.assertEqual(out_doc.get("outgrowerType"), "Company")

			sync_data = api.get_sync_data(last_sync="2000-01-01T00:00:00Z")
			outgrowers = sync_data.get("data", {}).get("outgrowers", [])
			self.assertTrue(outgrowers)
			out_mobile = [d for d in outgrowers if d.get("outgrowerId") == outgrower_name][0]
			self.assertEqual(out_mobile.get("bank_account"), "ACC-999")
			self.assertEqual(out_mobile.get("outgrower_type"), "Company")
			self.assertEqual(out_mobile.get("bankAccount"), "ACC-999")
			self.assertEqual(out_mobile.get("outgrowerType"), "Company")
		finally:
			if frappe.db.exists("Outgrower", outgrower_name):
				frappe.delete_doc("Outgrower", outgrower_name, force=1, ignore_permissions=True)
