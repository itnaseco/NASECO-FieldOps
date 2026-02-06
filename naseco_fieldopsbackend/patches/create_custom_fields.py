import frappe


def execute():
	"""Create required custom fields for standard doctypes."""
	from naseco_fieldopsbackend.setup_fieldops import create_cust_fields

	create_cust_fields()
	frappe.db.commit()
