import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


CORRELATED_DOCTYPES = (
	"Agronomy Report",
	"Crop Production Lot",
	"Field Corrective Action",
	"Seed Harvest Quality Assessment",
)


def execute():
	"""Give every mobile-created operational document an idempotency key."""
	fields = {
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
		for doctype in CORRELATED_DOCTYPES
	}
	create_custom_fields(fields, update=True)
