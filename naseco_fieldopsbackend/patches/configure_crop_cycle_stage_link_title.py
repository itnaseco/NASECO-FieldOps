"""Show stage names instead of generated IDs in Crop Cycle Stage links."""

from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	make_property_setter(
		"Crop Cycle Stage", None, "title_field", "stage_name", "Data", for_doctype=True
	)
	make_property_setter(
		"Crop Cycle Stage",
		None,
		"show_title_field_in_link",
		1,
		"Check",
		for_doctype=True,
	)
	make_property_setter(
		"Crop Cycle Stage",
		None,
		"search_fields",
		"stage_name,stage_code,crop_cycle",
		"Data",
		for_doctype=True,
	)
