from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			doctype: [
				{
					"fieldname": "external_id",
					"label": "Mobile External ID",
					"fieldtype": "Data",
					"unique": 1,
					"read_only": 1,
					"hidden": 1,
					"no_copy": 1,
					"description": "Stable mobile identifier used for idempotent create recovery.",
				}
			]
			for doctype in ("Expense Claim", "Leave Application", "Employee Advance")
		},
		update=True,
	)
