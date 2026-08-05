import frappe
from frappe.utils import cint, flt


def execute():
	reports = frappe.get_all("Agronomy Report", filters={"docstatus": 0}, pluck="name")
	for report_name in reports:
		report = frappe.get_doc("Agronomy Report", report_name)
		for row in report.results or []:
			row.value_captured = cint(
				bool(row.date_value)
				or bool((row.text_value or "").strip())
				or flt(row.numeric_value) != 0
				or bool((row.remarks or "").strip())
			)
		report.flags.ignore_agronomy_location_validation = True
		report.flags.ignore_mandatory = True
		report.save(ignore_permissions=True)
