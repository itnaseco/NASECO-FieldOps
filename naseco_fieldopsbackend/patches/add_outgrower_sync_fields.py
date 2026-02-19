import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Idempotently add sync-compatible fields to Outgrower."""
	custom_fields = {
		"Outgrower": [
			{
				"fieldname": "bank_account",
				"label": "Bank Account",
				"fieldtype": "Data",
				"insert_after": "assigned_supervisor",
			},
			{
				"fieldname": "outgrower_type",
				"label": "Outgrower Type",
				"fieldtype": "Select",
				"options": "Individual\nGroup\nCooperative\nCompany",
				"insert_after": "bank_account",
			},
		]
	}
	create_custom_fields(custom_fields, update=True)
	frappe.db.commit()
