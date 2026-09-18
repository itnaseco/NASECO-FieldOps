"""Display User full names in Link controls while retaining email IDs."""

from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	make_property_setter(
		"User", None, "title_field", "full_name", "Data", for_doctype=True
	)
	make_property_setter(
		"User", None, "show_title_field_in_link", 1, "Check", for_doctype=True
	)
