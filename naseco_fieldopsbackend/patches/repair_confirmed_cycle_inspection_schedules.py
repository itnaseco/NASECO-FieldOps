import frappe

from naseco_fieldopsbackend.inspection_scheduler import sync_crop_cycle_lifecycle


def execute():
	"""Repair confirmed cycles affected by the template-versioning rollout.

	The scheduler is idempotent: existing inspections are retained and only
	missing template/cycle combinations are created.
	"""
	for name in frappe.get_all(
		"Crop Cycle",
		filters={"planting_date_confirmed": 1},
		pluck="name",
	):
		doc = frappe.get_doc("Crop Cycle", name)
		sync_crop_cycle_lifecycle(doc)

