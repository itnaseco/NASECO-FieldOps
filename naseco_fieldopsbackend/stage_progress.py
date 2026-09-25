# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime

from naseco_fieldopsbackend.roles import OUTGROWER_MANAGER_ROLE, QUALITY_MANAGER_ROLE


STAGE_CLOSE_ROLES = {"System Manager", OUTGROWER_MANAGER_ROLE, QUALITY_MANAGER_ROLE}
FINISHED_ACTIVITY_STATUSES = {"completed", "submitted"}
FINISHED_INSPECTION_STATUSES = {"verified"}
ACTIVE_VISIT_STATUSES = ("in_progress", "ongoing")


def _normal(value):
	return str(value or "").strip().casefold().replace("-", " ").replace("_", " ")


def _require_close_role():
	roles = set(frappe.get_roles(frappe.session.user))
	if frappe.session.user != "Administrator" and not roles.intersection(STAGE_CLOSE_ROLES):
		frappe.throw(
			_("Only an Outgrower Manager, Quality Manager, or System Manager can close a crop-cycle stage."),
			frappe.PermissionError,
		)


def _blocker(doctype, name, title, status, reason):
	return {
		"doctype": doctype,
		"name": name,
		"title": title or name,
		"status": status,
		"reason": reason,
	}


def _resolve_stage(crop_cycle, stage=None):
	cycle = frappe.get_doc("Crop Cycle", crop_cycle)
	stage_name = stage or cycle.current_stage
	if not stage_name:
		frappe.throw(_("Crop Cycle {0} has no current stage.").format(crop_cycle))
	stage_doc = frappe.get_doc("Crop Cycle Stage", stage_name)
	if stage_doc.crop_cycle != cycle.name:
		frappe.throw(_("The selected stage does not belong to Crop Cycle {0}.").format(cycle.name))
	return cycle, stage_doc


def _stage_readiness(cycle, stage_doc):
	blockers = []
	activity_rows = frappe.get_all(
		"Stage Activity",
		filters={"crop_cycle": cycle.name, "stage": stage_doc.name, "mandatory": 1},
		fields=["name", "title", "status"],
		order_by="due_date asc, creation asc",
	)
	for row in activity_rows:
		if _normal(row.status) not in FINISHED_ACTIVITY_STATUSES:
			blockers.append(_blocker(
				"Stage Activity", row.name, row.title, row.status,
				_("Mandatory activity is not completed."),
			))

	report_names = frappe.get_all(
		"Agronomy Report",
		filters={"crop_cycle": cycle.name, "stage": stage_doc.name, "docstatus": ["<", 2]},
		pluck="name",
	)
	if stage_doc.get("agronomy_report"):
		report_names.append(stage_doc.agronomy_report)
	report_names = list(dict.fromkeys(report_names))
	for report_name in report_names:
		report = frappe.db.get_value(
			"Agronomy Report", report_name,
			["name", "report_number", "stage_name", "status", "docstatus"],
			as_dict=True,
		)
		if not report:
			blockers.append(_blocker(
				"Agronomy Report", report_name, report_name, "Missing",
				_("The stage's required agronomy report is missing."),
			))
			continue
		if report.docstatus != 1:
			blockers.append(_blocker(
				"Agronomy Report", report.name,
				report.report_number or report.stage_name or report.name,
				report.status,
				_("Agronomy report has not been submitted."),
			))

	inspection_rows = frappe.get_all(
		"Inspection",
		filters={"crop_cycle": cycle.name, "stage": stage_doc.name},
		fields=["name", "inspection_type", "status"],
		order_by="scheduled_date asc, creation asc",
	)
	for row in inspection_rows:
		if _normal(row.status) not in FINISHED_INSPECTION_STATUSES:
			blockers.append(_blocker(
				"Inspection", row.name, row.inspection_type or row.name, row.status,
				_("Quality inspection must be verified before closing the stage."),
			))

	visit_rows = frappe.get_all(
		"Field Visit",
		filters={
			"crop_cycle": cycle.name,
			"stage": stage_doc.name,
			"status": ["in", list(ACTIVE_VISIT_STATUSES)],
		},
		fields=["name", "visited_by", "status"],
		order_by="actual_start asc, creation asc",
	)
	for row in visit_rows:
		blockers.append(_blocker(
			"Field Visit", row.name, row.visited_by or row.name, row.status,
			_("An active Field Visit must be completed or cancelled."),
		))

	return {
		"ready": not blockers,
		"crop_cycle": cycle.name,
		"stage": stage_doc.name,
		"stage_name": stage_doc.stage_name,
		"stage_status": stage_doc.status,
		"stage_modified": str(stage_doc.modified),
		"counts": {
			"mandatory_activities": len(activity_rows),
			"agronomy_reports": len(report_names),
			"quality_inspections": len(inspection_rows),
			"active_visits": len(visit_rows),
			"blockers": len(blockers),
		},
		"blockers": blockers,
	}


@frappe.whitelist()
def get_stage_close_readiness(crop_cycle, stage=None):
	_require_close_role()
	cycle, stage_doc = _resolve_stage(crop_cycle, stage)
	if cycle.current_stage != stage_doc.name:
		frappe.throw(_("Only the current crop-cycle stage can be reviewed for closure."))
	return _stage_readiness(cycle, stage_doc)


@frappe.whitelist()
def close_current_crop_cycle_stage(
	crop_cycle,
	expected_stage,
	expected_stage_modified=None,
	closure_notes=None,
):
	"""Close the current stage and advance exactly once from Frappe Desk."""
	_require_close_role()
	# Serialize two managers clicking Close Stage at the same time.
	frappe.db.sql("SELECT name FROM `tabCrop Cycle` WHERE name=%s FOR UPDATE", (crop_cycle,))
	cycle, stage_doc = _resolve_stage(crop_cycle, expected_stage)
	frappe.db.sql("SELECT name FROM `tabCrop Cycle Stage` WHERE name=%s FOR UPDATE", (stage_doc.name,))

	if cycle.current_stage != stage_doc.name:
		frappe.throw(
			_("Crop Cycle {0} has already moved to another stage. Reload the form.").format(cycle.name),
			frappe.TimestampMismatchError,
		)
	if _normal(stage_doc.status) in {"completed", "skipped", "cancelled"}:
		frappe.throw(_("This stage is already closed."))
	if expected_stage_modified and str(stage_doc.modified) != str(expected_stage_modified):
		frappe.throw(
			_("The stage changed after the closure review. Review it again before closing."),
			frappe.TimestampMismatchError,
		)

	readiness = _stage_readiness(cycle, stage_doc)
	if not readiness["ready"]:
		frappe.throw(
			_("This stage cannot be closed because {0} required item(s) are still pending.").format(
				len(readiness["blockers"])
			),
			title=_("Stage Is Not Ready"),
		)

	closed_at = now_datetime()
	stage_values = {"status": "Completed", "completion_percentage": 100}
	stage_meta = frappe.get_meta("Crop Cycle Stage")
	if stage_meta.has_field("closed_by"):
		stage_values["closed_by"] = frappe.session.user
	if stage_meta.has_field("closed_at"):
		stage_values["closed_at"] = closed_at
	if stage_meta.has_field("closure_notes"):
		stage_values["closure_notes"] = (closure_notes or "").strip() or None
	frappe.db.set_value("Crop Cycle Stage", stage_doc.name, stage_values)

	next_rows = frappe.get_all(
		"Crop Cycle Stage",
		filters={
			"crop_cycle": cycle.name,
			"order_index": [">", stage_doc.order_index or 0],
			"status": ["not in", ["Completed", "Skipped", "Cancelled"]],
		},
		pluck="name",
		order_by="order_index asc",
		limit=1,
	)
	next_stage = next_rows[0] if next_rows else None
	if next_stage:
		next_values = {"status": "In Progress"}
		frappe.db.set_value("Crop Cycle Stage", next_stage, next_values)
		frappe.db.set_value("Crop Cycle", cycle.name, "current_stage", next_stage)
	else:
		# Keep the pointer on the completed final stage. Crop Cycle completion is
		# governed separately by the existing harvest lifecycle.
		next_stage = None

	stage_doc.add_comment(
		"Info",
		_("Stage closed by {0}.{1}").format(
			frappe.session.user,
			" " + (closure_notes or "").strip() if (closure_notes or "").strip() else "",
		),
	)
	return {
		"success": True,
		"crop_cycle": cycle.name,
		"closed_stage": stage_doc.name,
		"next_stage": next_stage,
		"closed_by": frappe.session.user,
		"closed_at": str(closed_at),
	}
