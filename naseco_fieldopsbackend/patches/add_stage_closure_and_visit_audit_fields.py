import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Crop Cycle Stage": [
				{
					"fieldname": "closed_by",
					"label": "Closed By",
					"fieldtype": "Link",
					"options": "User",
					"read_only": 1,
					"no_copy": 1,
					"insert_after": "completion_percentage",
				},
				{
					"fieldname": "closed_at",
					"label": "Closed At",
					"fieldtype": "Datetime",
					"read_only": 1,
					"no_copy": 1,
					"insert_after": "closed_by",
				},
				{
					"fieldname": "closure_notes",
					"label": "Closure Notes",
					"fieldtype": "Small Text",
					"read_only": 1,
					"no_copy": 1,
					"insert_after": "closed_at",
				},
			],
			"Field Visit": [
				{
					"fieldname": "completed_by",
					"label": "Completed By",
					"fieldtype": "Link",
					"options": "User",
					"read_only": 1,
					"no_copy": 1,
					"insert_after": "actual_end",
				},
			],
		},
		update=True,
	)
