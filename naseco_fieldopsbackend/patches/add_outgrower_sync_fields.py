import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Idempotently add sync-compatible fields to Outgrower."""
	meta = frappe.get_meta("Outgrower")
	to_create = []

	if not meta.has_field("bank_account"):
		to_create.append(
			{
				"fieldname": "bank_account",
				"label": "Bank Account",
				"fieldtype": "Data",
				"insert_after": "assigned_supervisor",
			}
		)

	if not meta.has_field("outgrower_type"):
		to_create.append(
			{
				"fieldname": "outgrower_type",
				"label": "Outgrower Type",
				"fieldtype": "Select",
				"options": "Individual\nGroup\nCooperative\nCompany",
				"insert_after": "bank_account",
			}
		)

	if to_create:
		create_custom_fields({"Outgrower": to_create}, update=True)
	frappe.db.commit()
