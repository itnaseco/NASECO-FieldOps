import frappe

from naseco_fieldopsbackend.api import _migrate_unstarted_scheduled_inspections


def execute():
	"""Backfill safe Scheduled inspections after configurable version rollout."""
	for name in frappe.get_all(
		"Inspection Template",
		filters={
			"lifecycle_status": "Published",
			"supersedes_template": ["is", "set"],
		},
		pluck="name",
	):
		_migrate_unstarted_scheduled_inspections(frappe.get_doc("Inspection Template", name))
