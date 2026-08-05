# Copyright (c) 2026, Naseco and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from naseco_fieldopsbackend import api
from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower.outgrower import (
	outgrower_supervisor_query,
)
from naseco_fieldopsbackend.roles import (
	OUTGROWER_SUPERVISOR_ROLE,
	ensure_fieldops_roles,
)


class TestOutgrower(FrappeTestCase):
	def test_assigned_supervisor_requires_outgrower_supervisor_role(self):
		token = frappe.generate_hash(length=8).lower()
		supervisor = f"fieldops-supervisor-{token}@example.com"
		ordinary_user = f"fieldops-user-{token}@example.com"
		outgrower_name = f"OG-SUP-{token}"

		ensure_fieldops_roles()
		self._create_system_user(supervisor, roles=[OUTGROWER_SUPERVISOR_ROLE])
		self._create_system_user(ordinary_user)

		try:
			results = outgrower_supervisor_query(
				"User",
				token,
				"name",
				0,
				20,
				{},
			)
			result_names = {row[0] for row in results}
			self.assertIn(supervisor, result_names)
			self.assertNotIn(ordinary_user, result_names)

			frappe.get_doc(
				{
					"doctype": "Outgrower",
					"outgrower_id": outgrower_name,
					"full_name": "Supervisor Validation Farmer",
					"registration_date": "2026-02-01",
					"assigned_supervisor": supervisor,
				}
			).insert(ignore_permissions=True)

			with self.assertRaises(frappe.ValidationError):
				frappe.get_doc(
					{
						"doctype": "Outgrower",
						"outgrower_id": f"{outgrower_name}-INVALID",
						"full_name": "Invalid Supervisor Farmer",
						"registration_date": "2026-02-01",
						"assigned_supervisor": ordinary_user,
					}
				).insert(ignore_permissions=True)
		finally:
			for name in (outgrower_name, f"{outgrower_name}-INVALID"):
				self._delete_outgrower_and_supplier(name)
			for user in (supervisor, ordinary_user):
				if frappe.db.exists("User", user):
					frappe.delete_doc(
						"User",
						user,
						force=1,
						ignore_permissions=True,
					)

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
			self._delete_outgrower_and_supplier(outgrower_name)

	def test_creating_outgrower_creates_linked_supplier(self):
		token = frappe.generate_hash(length=8).lower()
		outgrower_name = f"OG-SUPPLIER-{token}"

		try:
			outgrower = frappe.get_doc(
				{
					"doctype": "Outgrower",
					"outgrower_id": outgrower_name,
					"full_name": f"Automatic Supplier Farmer {token}",
					"phone": "+256700000001",
					"email": f"supplier-{token}@example.com",
					"registration_date": "2026-02-01",
					"outgrower_type": "Individual",
				}
			).insert(ignore_permissions=True)

			self.assertTrue(outgrower.supplier)
			supplier = frappe.get_doc("Supplier", outgrower.supplier)
			self.assertEqual(supplier.supplier_name, outgrower.full_name)
			self.assertEqual(supplier.supplier_type, "Individual")
			self.assertEqual(supplier.mobile_no, outgrower.phone)
			self.assertEqual(supplier.custom_outgrower, outgrower.name)
		finally:
			self._delete_outgrower_and_supplier(outgrower_name)

	def test_outgrowers_with_same_name_get_distinct_suppliers(self):
		token = frappe.generate_hash(length=8).lower()
		outgrower_names = [f"OG-DUPLICATE-{token}-1", f"OG-DUPLICATE-{token}-2"]
		full_name = f"Duplicate Name Farmer {token}"

		try:
			outgrowers = [
				frappe.get_doc(
					{
						"doctype": "Outgrower",
						"outgrower_id": outgrower_name,
						"full_name": full_name,
						"registration_date": "2026-02-01",
						"outgrower_type": "Individual",
					}
				).insert(ignore_permissions=True)
				for outgrower_name in outgrower_names
			]

			self.assertNotEqual(outgrowers[0].supplier, outgrowers[1].supplier)
			for outgrower in outgrowers:
				self.assertEqual(
					frappe.db.get_value("Supplier", outgrower.supplier, "supplier_name"),
					full_name,
				)
		finally:
			for outgrower_name in outgrower_names:
				self._delete_outgrower_and_supplier(outgrower_name)

	@staticmethod
	def _create_system_user(email, roles=None):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "FieldOps Test User",
				"enabled": 1,
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		if roles:
			user.add_roles(*roles)
		return user.name

	@staticmethod
	def _delete_outgrower_and_supplier(outgrower_name):
		if not frappe.db.exists("Outgrower", outgrower_name):
			return

		supplier = frappe.db.get_value("Outgrower", outgrower_name, "supplier")
		if supplier:
			frappe.db.set_value("Outgrower", outgrower_name, "supplier", None, update_modified=False)
			if frappe.db.exists("Supplier", supplier):
				if frappe.get_meta("Supplier").has_field("custom_outgrower"):
					frappe.db.set_value(
						"Supplier",
						supplier,
						"custom_outgrower",
						None,
						update_modified=False,
					)

		frappe.delete_doc("Outgrower", outgrower_name, force=1, ignore_permissions=True)
		if supplier and frappe.db.exists("Supplier", supplier):
			frappe.delete_doc("Supplier", supplier, force=1, ignore_permissions=True)
