import frappe


def execute():
	"""Link existing inspections to canonical lifecycle stages without changing work data."""
	from naseco_fieldopsbackend.inspection_scheduler import inspection_lifecycle_stage_name

	for inspection in frappe.get_all(
		"Inspection",
		filters={"stage": ["is", "not set"], "docstatus": ["<", 2]},
		fields=["name", "crop_cycle", "inspection_type"],
	):
		stage_name = inspection_lifecycle_stage_name(inspection.inspection_type)
		if not stage_name or not inspection.crop_cycle:
			continue
		stage = frappe.db.get_value(
			"Crop Cycle Stage",
			{"crop_cycle": inspection.crop_cycle, "stage_name": stage_name},
		)
		if stage:
			frappe.db.set_value(
				"Inspection", inspection.name, "stage", stage, update_modified=False
			)
