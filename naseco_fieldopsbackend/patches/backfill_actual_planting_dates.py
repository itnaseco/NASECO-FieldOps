import frappe


def execute():
	for report_name in frappe.get_all(
		"Agronomy Report",
		filters={"docstatus": 1, "report_number": 2},
		pluck="name",
	):
		report = frappe.get_doc("Agronomy Report", report_name)
		if any(
			row.parameter_code == "PLANTING_DATE" and row.date_value
			for row in report.results
		):
			report.sync_actual_planting_date()
