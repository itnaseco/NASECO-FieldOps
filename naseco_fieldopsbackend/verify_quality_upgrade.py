import frappe


def execute():
	return {
		"inspection_count": frappe.db.count("Inspection"),
		"non_cancelled_inspection_count": frappe.db.count("Inspection", {"status": ["!=", "Cancelled"]}),
		"templates": frappe.get_all(
			"Inspection Template",
			fields=["name", "active", "lifecycle_status", "configuration_version"],
			order_by="name",
		),
		"legacy_standard_count": frappe.db.count("Inspection Standard"),
		"template_parameter_count": frappe.db.count("Inspection Template Parameter"),
		"applicability_rule_count": frappe.db.count("Inspection Template Applicability"),
		"frozen_snapshot_count": frappe.db.count("Inspection", {"configuration_snapshot": ["is", "set"]}),
	}
