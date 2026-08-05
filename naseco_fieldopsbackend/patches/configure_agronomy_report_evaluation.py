import frappe

from naseco_fieldopsbackend.fixtures.seed_data import seed_agronomy_report_templates


def execute():
	seed_agronomy_report_templates()
	upgrade_open_reports()


def upgrade_open_reports():
	for report_name in frappe.get_all(
		"Agronomy Report",
		filters={"docstatus": 0},
		pluck="name",
	):
		report = frappe.get_doc("Agronomy Report", report_name)
		report.flags.refresh_agronomy_standard_snapshot = True
		report.flags.ignore_agronomy_location_validation = True
		report.flags.ignore_mandatory = True
		report.save(ignore_permissions=True)
