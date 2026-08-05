import frappe

from naseco_fieldopsbackend.naseco_fieldopsbackend.page.season_command_centre.season_command_centre import (
	get_command_centre,
)
from naseco_fieldopsbackend.roles import FIELDOPS_ROLES
from naseco_fieldopsbackend.season_reports import (
	agronomy_progress,
	grower_acreage,
	harvest_settlement,
	input_exposure,
	inspector_performance,
	production_performance,
	qa_coverage,
)


def verify_operating_model():
	filters = {
		"season": "2026 B",
		"company": frappe.defaults.get_global_default("company"),
	}
	report_functions = {
		"Season Production Performance": production_performance,
		"Season Grower and Acreage Progress": grower_acreage,
		"Season Agronomy Progress": agronomy_progress,
		"Season QA Coverage": qa_coverage,
		"Season Inspector Performance": inspector_performance,
		"Season Input and Exposure": input_exposure,
		"Season Harvest and Settlement": harvest_settlement,
	}
	report_rows = {}
	for report_name, function in report_functions.items():
		columns, rows = function(filters)
		if not columns:
			raise AssertionError(f"{report_name} has no columns")
		report_rows[report_name] = len(rows)

	command_centre = get_command_centre(season=filters["season"])
	if not command_centre.get("plan"):
		raise AssertionError("Season Command Centre has no production plan")

	return {
		"roles": {
			role: bool(frappe.db.exists("Role", role))
			for role in FIELDOPS_ROLES
		},
		"role_profiles": frappe.db.count(
			"Role Profile", {"name": ["like", "FieldOps%"]}
		),
		"active_workflow": frappe.db.get_value(
			"Workflow",
			"Season Production Plan Approval",
			["document_type", "is_active"],
			as_dict=True,
		),
		"command_centre_plan": command_centre["plan"]["name"],
		"command_centre_targets": len(command_centre["targets"]),
		"report_rows": report_rows,
		"workspace": bool(frappe.db.exists("Workspace", "NASECO FieldOps")),
		"page": bool(frappe.db.exists("Page", "season-command-centre")),
	}
