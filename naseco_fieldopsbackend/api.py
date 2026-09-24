# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
import io
import os
import base64
from collections import defaultdict
from datetime import datetime
from frappe.utils import cint, flt, get_fullname

from naseco_fieldopsbackend.uom import normalize_uom
from naseco_fieldopsbackend.roles import (
	OUTGROWER_MANAGER_ROLE,
	OUTGROWER_SUPERVISOR_ROLE,
	QUALITY_INSPECTOR_ROLE,
	QUALITY_MANAGER_ROLE,
)


def _contains_file_reference(value, file_url):
	"""Return true when a document/child-table value references file_url."""
	if isinstance(value, str):
		return value.strip() == file_url
	if isinstance(value, dict):
		return any(_contains_file_reference(item, file_url) for item in value.values())
	if isinstance(value, (list, tuple)):
		return any(_contains_file_reference(item, file_url) for item in value)
	return False


def _valid_image_content(content, file_name=None):
	if not isinstance(content, (bytes, bytearray)) or len(content) < 12:
		return False
	name = (file_name or "").lower()
	if name.endswith(".png"):
		return content.startswith(b"\x89PNG\r\n\x1a\n")
	if name.endswith((".jpg", ".jpeg")):
		return content.startswith(b"\xff\xd8")
	if name.endswith(".gif"):
		return content.startswith((b"GIF87a", b"GIF89a"))
	if name.endswith(".webp"):
		return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
	return content.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8", b"GIF87a", b"GIF89a"))


@frappe.whitelist()
def upload_mobile_media(filename, filedata, is_private=1):
	"""Save an authenticated mobile attachment from exact base64 bytes.

	Frappe's modern upload_file endpoint only reads multipart request.files and
	ignores JSON filedata. Keeping this transport explicit prevents binary data
	from being text-reencoded by mobile/proxy multipart implementations.
	"""
	from frappe.utils import cint
	from frappe.utils.file_manager import save_file

	filename = os.path.basename((filename or "").strip())
	if not filename or not filedata:
		frappe.throw(_("A filename and file data are required."), frappe.ValidationError)
	try:
		content = base64.b64decode(filedata, validate=True)
	except Exception:
		frappe.throw(_("The uploaded file is not valid base64 data."), frappe.ValidationError)
	if not content or len(content) > 25 * 1024 * 1024:
		frappe.throw(_("The uploaded file is empty or exceeds the 25 MB mobile limit."), frappe.ValidationError)
	image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp")
	if filename.lower().endswith(image_extensions) and not _valid_image_content(content, filename):
		frappe.throw(_("The uploaded image is corrupt or incomplete."), frappe.ValidationError)
	file_doc = save_file(
		filename,
		content,
		dt=None,
		dn=None,
		is_private=cint(is_private),
	)
	return {
		"name": file_doc.name,
		"file_name": file_doc.file_name,
		"file_url": file_doc.file_url,
		"is_private": file_doc.is_private,
		"file_size": file_doc.file_size,
	}


def _mobile_file_is_in_scope(file_doc):
	"""Authorize a File through the same assignment scope used by mobile sync.

	Mobile uploads can be unattached private Files whose URL is stored in a
	document or child row. Therefore checking File.owner or attached_to_name is
	not enough when a supervisor uploads media later needed by an assigned
	quality inspector.
	"""
	doctype = file_doc.get("attached_to_doctype")
	name = file_doc.get("attached_to_name")
	if doctype and name and doctype in _mobile_allowed_doctypes("read"):
		if _mobile_record_is_in_scope(doctype, name=name):
			return True

	media_doctypes = (
		"Farm Plot",
		"Field Visit",
		"Inspection",
		"Stage Activity",
		"Stage Input Dispatch",
		"Leave Application",
		"Employee Advance",
		"Expense Claim",
	)
	for candidate in media_doctypes:
		if candidate not in _mobile_allowed_doctypes("read"):
			continue
		names = _mobile_scope_names(candidate)
		if not names:
			continue
		for doc_name in names:
			try:
				doc = frappe.get_doc(candidate, doc_name).as_dict()
			except Exception:
				continue
			if _contains_file_reference(doc, file_doc.file_url):
				return True
	return False


@frappe.whitelist()
def download_mobile_media(file_url):
	"""Download media referenced by a document in the caller's mobile scope."""
	file_url = (file_url or "").strip()
	if not file_url or not file_url.startswith(("/files/", "/private/files/")):
		frappe.throw(_("Invalid mobile media URL."), frappe.ValidationError)
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("Media file was not found."), frappe.DoesNotExistError)
	file_doc = frappe.get_doc("File", file_name)
	if not _mobile_file_is_in_scope(file_doc):
		frappe.throw(_("You are not permitted to download this mobile media file."), frappe.PermissionError)
	content = file_doc.get_content()
	if (file_doc.file_name or "").lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")) and not _valid_image_content(content, file_doc.file_name):
		frappe.throw(_("The stored image is corrupt and must be regenerated."), frappe.ValidationError)
	frappe.local.response.filename = file_doc.file_name
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"


def _plot_polygon_preview(doc):
	from PIL import Image, ImageDraw

	points = []
	for row in doc.get("polygon") or []:
		lat = row.get("latitude")
		lng = row.get("longitude")
		if lat is not None and lng is not None:
			points.append((float(lng), float(lat)))
	if len(points) < 3:
		return None
	width, height, padding = 1200, 800, 90
	min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
	min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
	x_span = max(max_x - min_x, 0.0000001)
	y_span = max(max_y - min_y, 0.0000001)
	mapped = [
		(
			padding + ((x - min_x) / x_span) * (width - padding * 2),
			padding + ((max_y - y) / y_span) * (height - padding * 2),
		)
		for x, y in points
	]
	image = Image.new("RGB", (width, height), "#edf4f1")
	draw = ImageDraw.Draw(image)
	draw.polygon(mapped, fill="#b9ded3", outline="#006b5d", width=12)
	buffer = io.BytesIO()
	image.save(buffer, format="PNG", optimize=True)
	return buffer.getvalue()


@frappe.whitelist()
def repair_corrupt_plot_map_images():
	"""Replace only corrupt/missing Farm Plot images with polygon previews."""
	_require_quality_manager()
	from frappe.utils.file_manager import save_file

	repaired = []
	skipped = []
	for name in frappe.get_all("Farm Plot", pluck="name"):
		doc = frappe.get_doc("Farm Plot", name)
		file_url = (doc.get("map_image_base64") or "").strip()
		valid = False
		if file_url:
			file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
			if file_name:
				file_doc = frappe.get_doc("File", file_name)
				try:
					valid = _valid_image_content(file_doc.get_content(), file_doc.file_name)
				except Exception:
					valid = False
		if valid:
			continue
		preview = _plot_polygon_preview(doc)
		if not preview:
			skipped.append(name)
			continue
		new_file = save_file(
			f"plot_{frappe.scrub(name)}_recovered.png",
			preview,
			"Farm Plot",
			name,
			is_private=0,
		)
		doc.db_set("map_image_base64", new_file.file_url, update_modified=False)
		repaired.append(name)
	frappe.db.commit()
	return {"repaired": repaired, "skipped_without_polygon": skipped}


def _require_quality_manager():
	roles = frappe.get_roles()
	if frappe.session.user != "Administrator" and QUALITY_MANAGER_ROLE not in roles and "System Manager" not in roles:
		frappe.throw(_("Only a Quality Manager can manage published inspection configurations."), frappe.PermissionError)


@frappe.whitelist()
def create_inspection_template_version(template):
	"""Clone a published template and its standards into an editable draft version."""
	_require_quality_manager()
	source = frappe.get_doc("Inspection Template", template)
	next_version = cint(source.get("configuration_version")) + 1
	base_name = source.template_name.rsplit(" v", 1)[0]
	new_name = f"{base_name} v{next_version}"
	if frappe.db.exists("Inspection Template", new_name):
		return {"name": new_name, "version": next_version}
	clone = frappe.copy_doc(source)
	clone.template_name = new_name
	clone.configuration_version = next_version
	clone.lifecycle_status = "Draft"
	clone.supersedes_template = source.name
	clone.active = 0
	clone.effective_from = None
	clone.effective_to = None
	clone.insert(ignore_permissions=True)
	for standard in frappe.get_all(
		"Inspection Standard",
		filters={"inspection_template": source.name},
		pluck="name",
	):
		row = frappe.copy_doc(frappe.get_doc("Inspection Standard", standard))
		row.inspection_template = clone.name
		row.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": clone.name, "version": next_version}


@frappe.whitelist()
def publish_inspection_template_version(template):
	"""Publish a draft version and retire only the version it supersedes."""
	_require_quality_manager()
	doc = frappe.get_doc("Inspection Template", template)
	if doc.lifecycle_status == "Published":
		migrated = _migrate_unstarted_scheduled_inspections(doc)
		frappe.db.commit()
		return {"name": doc.name, "version": doc.configuration_version, "migrated_inspections": migrated}
	if doc.lifecycle_status != "Draft":
		frappe.throw(_("Only a Draft inspection template can be published."))
	parameter_rows = doc.get("quality_parameters") or []
	if not parameter_rows and not frappe.db.exists("Inspection Standard", {"inspection_template": doc.name}):
		frappe.throw(_("Add at least one Inspection Standard before publishing this template."))
	if parameter_rows:
		_materialize_template_parameter_standards(doc)
	if doc.supersedes_template and frappe.db.exists("Inspection Template", doc.supersedes_template):
		frappe.db.set_value(
			"Inspection Template",
			doc.supersedes_template,
			{"lifecycle_status": "Retired", "active": 0, "effective_to": frappe.utils.today()},
		)
	doc.db_set(
		{"lifecycle_status": "Published", "active": 1, "effective_from": doc.effective_from or frappe.utils.today()},
	)
	migrated = _migrate_unstarted_scheduled_inspections(doc)
	frappe.db.commit()
	return {"name": doc.name, "version": doc.configuration_version, "migrated_inspections": migrated}


def _materialize_template_parameter_standards(template_doc):
	"""Maintain legacy Inspection Standard rows for existing server logic.

	Draft versions are not used by inspections, so rebuilding only that draft's
	compatibility rows cannot change historical inspections.
	"""
	for name in frappe.get_all(
		"Inspection Standard",
		filters={"inspection_template": template_doc.name},
		pluck="name",
	):
		frappe.delete_doc("Inspection Standard", name, ignore_permissions=True)
	for row in template_doc.get("quality_parameters") or []:
		if not cint(row.active):
			continue
		frappe.get_doc(
			{
				"doctype": "Inspection Standard",
				"inspection_template": template_doc.name,
				"parameter": row.parameter,
				"production_category": row.production_category,
				"seed_class": row.seed_class,
				"section_label": row.section_label,
				"display_order": row.display_order,
				"mandatory": row.mandatory,
				"comparison_rule": row.comparison_rule,
				"minimum_value": row.minimum_value,
				"maximum_value": row.maximum_value,
				"expected_text": row.expected_text,
				"unit": row.unit,
				"good_label": row.good_label,
				"poor_label": row.poor_label,
				"aggregation_method": row.aggregation_method,
				"auto_reject_on_fail": row.auto_reject_on_fail,
				"corrective_action_on_fail": row.corrective_action_on_fail,
				"standard_notes": row.standard_notes,
			}
		).insert(ignore_permissions=True)


def _migrate_unstarted_scheduled_inspections(template_doc):
	"""Move untouched Scheduled inspections along an explicit version chain.

	Inspections with any captured field evidence remain pinned to their frozen
	snapshot. Updating `modified` is intentional so incremental mobile sync pulls
	the replacement capture schema immediately.
	"""
	source = template_doc.get("supersedes_template")
	if not source:
		return []
	snapshot = _inspection_configuration_snapshot(template_doc.name)
	migrated = []
	for name in frappe.get_all(
		"Inspection",
		filters={
			"inspection_template": source,
			"status": "Scheduled",
			"docstatus": ["<", 2],
		},
		pluck="name",
	):
		if any(
			frappe.db.count(child, {"parent": name})
			for child in (
				"Inspection Take",
				"Inspection Take Result",
				"Inspection Take Evidence",
				"Inspection Observation",
				"Inspection Result",
			)
		):
			continue
		frappe.db.set_value(
			"Inspection",
			name,
			{
				"inspection_template": template_doc.name,
				"template_version": template_doc.configuration_version or 1,
				"configuration_snapshot": snapshot,
			},
			update_modified=True,
		)
		migrated.append(name)
	return migrated

# Mobile <-> Frappe mappings
BASE_STORE_TO_DOCTYPE = {
	"outgrowers": "Outgrower",
	"plots": "Farm Plot",
	"crop_cycles": "Crop Cycle",
	"outgrower_production_contracts": "Outgrower Production Contract",
	"production_contract_templates": "Production Contract Template",
	"outgrower_pricing_policies": "Outgrower Pricing Policy",
	"crop_cycle_stages": "Crop Cycle Stage",
	"crop_production_lots": "Crop Production Lot",
	"seed_harvest_quality_assessments": "Seed Harvest Quality Assessment",
	"visits": "Field Visit",
	"field_trips": "Field Trip",
	"inspections": "Inspection",
	"inspection_templates": "Inspection Template",
	"inspection_parameters": "Inspection Parameter",
	"inspection_standards": "Inspection Standard",
	"inspection_template_parameters": "Inspection Template Parameter",
	"inspection_template_applicability": "Inspection Template Applicability",
	"agronomy_activity_templates": "Agronomy Activity Template",
	"agronomy_report_templates": "Agronomy Report Template",
	"agronomy_reports": "Agronomy Report",
	"field_corrective_actions": "Field Corrective Action",
	"corrective_actions": "Field Corrective Action",
	"plot_crop_assignments": "Plot Crop Assignment",
	"plot_assignments": "Plot Crop Assignment",
	"stage_activities": "Stage Activity",
	"stage_input_requests": "Stage Input Request",
	"stage_input_dispatches": "Stage Input Dispatch",
	"crop_cycle_advance_requests": "Crop Cycle Advance Request",
	"crop_cycle_settlements": "Crop Cycle Settlement",
	"attendance": "Attendance",
	"employee_checkins": "Employee Checkin",
	"expense_requests": "Expense Claim",
	"expenses": "Expense Claim",
	"leave_applications": "Leave Application",
	"leaves": "Leave Application",
	"salary_advances": "Employee Advance",
	"advances": "Employee Advance",
	"crops": "Crop",
	"varieties": "Crop Variety",
	"seasons": "Season",
	"crop_recipes": "Crop Recipe",
	"recipe_stages": "Recipe Stage",
	"recipe_inputs": "Recipe Input Item",
	"visit_types": "Visit Type",
	"regions": "Region",
	"units": "UOM",
	"inspection_attributes": "Inspection Attribute",
}

STORE_TO_DOCTYPE = dict(BASE_STORE_TO_DOCTYPE)
STORE_TO_DOCTYPE.update({
	"OutGrower": "Outgrower",
	"Plot": "Farm Plot",
	"CropCycle": "Crop Cycle",
	"OutgrowerProductionContract": "Outgrower Production Contract",
	"ProductionContractTemplate": "Production Contract Template",
	"OutgrowerPricingPolicy": "Outgrower Pricing Policy",
	"CropCycleStage": "Crop Cycle Stage",
	"CropProductionLot": "Crop Production Lot",
	"SeedHarvestQualityAssessment": "Seed Harvest Quality Assessment",
	"Visit": "Field Visit",
	"FieldTrip": "Field Trip",
	"Inspection": "Inspection",
	"InspectionTemplate": "Inspection Template",
	"InspectionParameter": "Inspection Parameter",
	"InspectionStandard": "Inspection Standard",
	"InspectionTemplateParameter": "Inspection Template Parameter",
	"InspectionTemplateApplicability": "Inspection Template Applicability",
	"AgronomyActivityTemplate": "Agronomy Activity Template",
	"AgronomyReportTemplate": "Agronomy Report Template",
	"AgronomyReport": "Agronomy Report",
	"FieldCorrectiveAction": "Field Corrective Action",
	"PlotCropAssignment": "Plot Crop Assignment",
	"StageActivity": "Stage Activity",
	"StageInputRequest": "Stage Input Request",
	"StageInputDispatch": "Stage Input Dispatch",
	"CropCycleAdvanceRequest": "Crop Cycle Advance Request",
	"CropCycleSettlement": "Crop Cycle Settlement",
	"Crop": "Crop",
	"Variety": "Crop Variety",
	"Season": "Season",
	"CropRecipe": "Crop Recipe",
	"RecipeStage": "Recipe Stage",
	"RecipeInput": "Recipe Input Item",
	"VisitType": "Visit Type",
	"Region": "Region",
	"Unit": "UOM",
	"UOM": "UOM",
	"InspectionAttribute": "Inspection Attribute",
})

MOBILE_REFERENCE_DOCTYPES = {
	"Crop",
	"Crop Variety",
	"Season",
	"Crop Recipe",
	"Visit Type",
	"Region",
	"UOM",
	"Inspection Attribute",
	"Inspection Parameter",
	"Inspection Template",
	"Inspection Standard",
	"Inspection Template Parameter",
	"Inspection Template Applicability",
	"Agronomy Activity Template",
	"Agronomy Report Template",
	"Crop Cycle Stage",
}
MOBILE_CONTEXT_DOCTYPES = {
	"Outgrower",
	"Farm Plot",
	"Crop Cycle",
	"Outgrower Production Contract",
	"Crop Production Lot",
}
MOBILE_HR_SELF_SERVICE_DOCTYPES = {
	"Expense Claim",
	"Leave Application",
	"Employee Advance",
}
MOBILE_ROLE_READ = {
	OUTGROWER_SUPERVISOR_ROLE: MOBILE_CONTEXT_DOCTYPES
	| {
		"Field Visit",
		"Field Trip",
		"Agronomy Report",
		"Field Corrective Action",
		"Plot Crop Assignment",
		"Stage Activity",
		"Stage Input Request",
		"Stage Input Dispatch",
		"Stage Input Dispatch",
	},
	QUALITY_INSPECTOR_ROLE: MOBILE_CONTEXT_DOCTYPES
	| {
		"Field Visit",
		"Field Trip",
		"Inspection",
		"Field Corrective Action",
		"Seed Harvest Quality Assessment",
	},
}
MOBILE_ROLE_WRITE = {
	OUTGROWER_SUPERVISOR_ROLE: {
		"Outgrower",
		"Farm Plot",
		"Field Visit",
		"Field Trip",
		"Agronomy Report",
		"Field Corrective Action",
		"Stage Activity",
		"Stage Input Dispatch",
	},
	QUALITY_INSPECTOR_ROLE: {
		"Field Visit",
		"Field Trip",
		"Inspection",
		"Field Corrective Action",
		"Seed Harvest Quality Assessment",
	},
}
MOBILE_ROLE_CREATE = {
	OUTGROWER_SUPERVISOR_ROLE: {
		"Outgrower",
		"Farm Plot",
		"Field Visit",
		"Field Trip",
		"Stage Activity",
		"Stage Input Dispatch",
	},
	QUALITY_INSPECTOR_ROLE: {"Field Visit", "Field Trip", "Inspection", "Seed Harvest Quality Assessment"},
}
MOBILE_SERVER_OWNED_FIELDS = {
	"Leave Application": {"status", "leave_approver", "workflow_state"},
	"Employee Advance": {"status", "workflow_state", "paid_amount", "claimed_amount"},
	"Expense Claim": {
		"status", "workflow_state", "approval_status", "total_claimed_amount",
		"total_sanctioned_amount", "total_amount_reimbursed",
	},
	"Farm Plot": {
		# Derived exclusively from the linked Crop Cycle lifecycle. Accepting the
		# mobile cache's older value can incorrectly revert an occupied plot.
		"status",
	},
	"Inspection": {
		"status",
		"assigned_to",
		"qa_review_status",
		"qa_reviewed_by",
		"qa_reviewed_on",
		"qa_review_notes",
		"reinspection_of",
		"reinspection_reason",
		"sampling_protocol_version",
		"template_version",
		"configuration_snapshot",
		"results",
		"completed_take_count",
		"farmer_compliance_percent",
		"farmer_compliance_status",
		"supervisor_compliance_percent",
		"supervisor_compliance_status",
		"field_certification_status",
		"controls_completed",
		"cumulative_total_plants",
	},
	"Agronomy Report": {
		"status",
		"report_template",
		"report_number",
		"crop_cycle",
		"stage",
		"stage_name",
		"production_contract",
		"plot",
		"outgrower",
		"crop",
		"variety",
		"season",
		"production_category",
		"assigned_supervisor",
		"window_start_date",
		"window_end_date",
		"overall_result",
		"pass_percentage",
		"evaluated_parameter_count",
		"passed_parameter_count",
		"failed_parameter_count",
		"critical_failure_count",
		"evaluated_at",
		"template_version",
		"overall_pass_threshold_percent",
		"critical_failure_override",
		"summary",
		"corrective_action_required",
		"corrective_action",
		"corrective_action_due_date",
		"submitted_by",
		"submitted_at",
	},
	"Seed Harvest Quality Assessment": {"assessment_status", "verified_by"},
	"Field Corrective Action": {"verified_by", "verified_on", "closed_on"},
	"Stage Activity": {
		"stage_lock_override_by",
		"stage_lock_override_at",
		"stage_lock_override_reason",
	},
	"Stage Input Dispatch": {
		"stock_entry",
		"stock_entry_detail",
		"workflow_status",
		"quantity_dispatched",
		"dispatched_by",
	},
}
MOBILE_SERVER_OWNED_FIELDS["Agronomy Report"] |= {
	"stage_lock_override_by",
	"stage_lock_override_at",
	"stage_lock_override_reason",
	"location_boundary_override_by",
	"location_boundary_override_at",
}

# Doctypes whose field data may only be created/updated while their linked
# Crop Cycle Stage is the crop cycle's current stage (see _mobile_stage_lock_error).
# Inspection is intentionally excluded: it has no `stage` link field server-side,
# the mobile client only groups inspections to a stage for display.
STAGE_LOCKED_DOCTYPES = {
	"Stage Activity", "Agronomy Report", "Inspection", "Stage Input Dispatch"
}
# A record whose stage closed within this many days is still editable, so a
# device that was offline right at the stage boundary isn't blocked outright.
STAGE_EDIT_GRACE_DAYS = 1

DOCTYPE_TO_STORE = {v: k for k, v in BASE_STORE_TO_DOCTYPE.items()}
# Input aliases must not choose the outbound canonical mobile store.
DOCTYPE_TO_STORE["Field Corrective Action"] = "field_corrective_actions"

# Doctypes with no Table/child-table fields (verified against each doctype's
# JSON). get_sync_data can fetch these with a single bulk frappe.get_all(...)
# call instead of one frappe.get_doc() per record — the latter issues an
# extra query per child table per row and was the main cause of the sync
# endpoint timing out as Attendance/Employee Checkin accumulate daily
# records. Doctypes with real child tables (Farm Plot, Crop Cycle, Crop
# Cycle Stage, Field Visit, Inspection, Agronomy Report, Stage Input
# Request) keep the slower get_doc() path since _map_doc_to_mobile needs
# their nested data.
SYNC_DOCTYPES_WITHOUT_CHILD_TABLES = {
	"Outgrower",
	"Field Trip",
	"Field Corrective Action",
	"Plot Crop Assignment",
	"Stage Activity",
	"Stage Input Dispatch",
	"Crop Production Lot",
	"Seed Harvest Quality Assessment",
	"Attendance",
	"Employee Checkin",
	"Leave Application",
	"Employee Advance",
}

ID_FIELD_MAP = {
	"Expense Claim": "external_id",
	"Leave Application": "external_id",
	"Employee Advance": "external_id",
	"Outgrower": "outgrower_id",
	"Farm Plot": "plot_id",
	"Crop Cycle": "crop_cycle_id",
	"Crop Production Lot": "external_id",
	"Seed Harvest Quality Assessment": "external_id",
	"Crop Cycle Stage": "stage_id",
	"Agronomy Report": "external_id",
	"Field Visit": "visit_id",
	"Field Trip": "external_id",
	"Inspection": "inspection_id",
	"Plot Crop Assignment": "assignment_id",
	"Stage Activity": "activity_id",
	"Stage Input Request": "request_id",
	"Stage Input Dispatch": "dispatch_id",
	"Crop": "crop_id",
	"Crop Variety": "variety_id",
	"Season": "season_id",
	"Crop Recipe": "recipe_id",
	"Visit Type": "visit_type_id",
}

MOBILE_FIELD_MAP = {
	"Outgrower": {
		"outgrowerId": "outgrower_id",
		"fullName": "full_name",
		"registrationDate": "registration_date",
		"yearsSinceRegistration": "years_since_registration",
		"assignedTo": "assigned_to",
		"assignedSupervisor": "assigned_supervisor",
		"bankAccount": "bank_account",
		"defaultBankAccount": "default_bank_account",
		"nationalId": "national_id",
		"village": "village",
		"subCounty": "sub_county",
		"district": "district",
		"eligibilityStatus": "eligibility_status",
		"consecutiveLowPuritySeasons": "consecutive_low_purity_seasons",
		"outgrowerType": "outgrower_type",
		"supplierId": "supplier",
	},
	"Farm Plot": {
		"plotId": "plot_id",
		"outgrowerId": "outgrower",
		"plotName": "plot_name",
		"plotType": "plot_type",
		"areaHectares": "area_hectares",
		"centroidLat": "centroid_lat",
		"centroidLng": "centroid_lng",
		"perimeterMeters": "perimeter_meters",
		"mapImageBase64": "map_image_base64",
	},
	"Crop": {
		"cropId": "crop_id",
		"cropName": "crop_name",
	},
	"Crop Variety": {
		"varietyId": "variety_id",
		"cropId": "crop",
		"maturityPeriodDays": "maturity_period_days",
		"expectedYieldKgPerHectare": "expected_yield_kg_per_hectare",
	},
	"Season": {
		"seasonId": "season_id",
		"seasonName": "season_name",
		"seasonStatus": "season_status",
		"startDate": "start_date",
		"endDate": "end_date",
	},
	"Crop Cycle": {
		"cropCycleId": "crop_cycle_id",
		"productionContractId": "production_contract",
		"plotId": "plot",
		"cropId": "crop",
		"varietyId": "variety",
		"seasonId": "season",
		"startDate": "start_date",
		"plantingDate": "planting_date",
		"productionCategory": "production_category",
		"samplingProtocolVersion": "sampling_protocol_version",
		"expectedHarvestDate": "expected_harvest_date",
		"currentStageId": "current_stage",
		"nextInspectionDate": "next_inspection_date",
		"companyId": "company",
		"supplierId": "supplier",
		"pricingPolicyId": "pricing_policy",
		"contractedAreaHectares": "contracted_area_hectares",
		"expectedYieldKgPerHectare": "expected_yield_kg_per_hectare",
		"contractedQuotaQty": "contracted_quota_qty",
		"harvestItemId": "harvest_item",
		"harvestUom": "harvest_uom",
		"expectedYieldQty": "expected_yield_qty",
		"contractRate": "contract_rate",
		"expectedHarvestValue": "expected_harvest_value",
		"maxExposurePercent": "max_exposure_percent",
		"purchaseOrderId": "purchase_order",
		"recoverableStockValue": "recoverable_stock_value",
		"cashAdvanced": "cash_advanced",
		"pendingCashAdvance": "pending_cash_advance",
		"totalExposure": "total_exposure",
		"availableAdvanceCapacity": "available_advance_capacity",
		"actualHarvestValue": "actual_harvest_value",
		"forecastNetPayable": "forecast_net_payable",
		"verifiedInterRowSpacingM": "verified_inter_row_spacing_m",
		"spacingSourceInspection": "spacing_source_inspection",
		"spacingVerifiedOn": "spacing_verified_on",
	},
	"Outgrower Production Contract": {
		"productionContractId": "name",
		"contractTemplateId": "contract_template",
		"contractTemplateVersion": "template_version",
		"pricingPolicyId": "pricing_policy",
		"pricingPolicyVersion": "pricing_policy_version",
		"outgrowerId": "outgrower",
		"supplierId": "supplier",
		"companyId": "company",
		"plotId": "farm_plot",
		"cropCycleId": "linked_crop_cycle",
		"seasonId": "season",
		"cropId": "crop",
		"varietyId": "variety",
		"productionCategory": "production_category",
		"cropRecipeId": "crop_recipe",
		"contractStartDate": "contract_start_date",
		"contractEndDate": "contract_end_date",
		"plantingStartDate": "planting_start_date",
		"plantingEndDate": "planting_end_date",
		"expectedHarvestDate": "expected_harvest_date",
		"harvestItemId": "harvest_item",
		"harvestUom": "harvest_uom",
		"expectedYieldQty": "expected_yield_qty",
		"pricingMethod": "pricing_method",
		"contractRate": "contract_rate",
		"currency": "currency",
		"expectedHarvestValue": "expected_harvest_value",
		"maxExposurePercent": "max_exposure_percent",
		"defaultRecoveryPolicy": "default_recovery_policy",
		"minimumFarmerCompliancePercent": "minimum_farmer_compliance_percent",
		"minimumSupervisorCompliancePercent": "minimum_supervisor_compliance_percent",
		"requiredIsolationQuality": "required_isolation_quality",
		"targetTakeSpacingM": "target_take_spacing_m",
		"contractedAreaHectares": "contracted_area_hectares",
		"expectedYieldKgPerHectare": "expected_yield_kg_per_hectare",
		"quotaKgPerHectare": "quota_kg_per_hectare",
		"contractedQuotaQty": "contracted_quota_qty",
		"parentSeedItemId": "parent_seed_item",
		"parentSeedQty": "planned_parent_seed_qty",
		"parentSeedUom": "parent_seed_uom",
		"agreementDate": "agreement_date",
		"isSigned": "is_signed",
		"signedOn": "signed_on",
		"erpnextContractId": "erpnext_contract",
		"parentSeeds": "parent_seed_items",
	},
	"Contract Parent Seed Item": {
		"parentRole": "parent_role",
		"parentSeedItemId": "item",
		"quantityPerHectare": "quantity_kg_per_hectare",
		"uom": "uom",
		"plannedQuantity": "planned_quantity",
		"rate": "rate",
		"plannedValue": "amount",
	},
	"Crop Production Lot": {
		"lotId": "name",
		"lotNumber": "lot_number",
		"status": "status",
		"cropCycleId": "crop_cycle",
		"productionContractId": "production_contract",
		"plotId": "plot",
		"outgrowerId": "outgrower",
		"seasonId": "season",
		"cropId": "crop",
		"varietyId": "variety",
		"plantingStartDate": "planting_start_date",
		"plantingEndDate": "planting_end_date",
		"areaHectares": "area_hectares",
		"acceptedAreaHectares": "accepted_area_hectares",
		"rejectedAreaHectares": "rejected_area_hectares",
		"parentSeedItemId": "parent_seed_item",
		"parentSeedBatchId": "parent_seed_batch",
		"harvestBatchId": "harvest_batch",
		"deliveredQty": "delivered_qty",
	},
	"Seed Harvest Quality Assessment": {
		"assessmentId": "name",
		"assessmentStatus": "assessment_status",
		"cropCycleId": "crop_cycle",
		"productionContractId": "production_contract",
		"productionLotId": "production_lot",
		"outgrowerId": "outgrower",
		"seasonId": "season",
		"pricingPolicyId": "pricing_policy",
		"purchaseReceiptId": "purchase_receipt",
		"purchaseReceiptItemId": "purchase_receipt_item",
		"qualityInspectionId": "quality_inspection",
		"itemCode": "item_code",
		"batchNo": "batch_no",
		"deliveryDate": "delivery_date",
		"grossQty": "gross_qty",
		"uom": "uom",
		"moisturePercent": "moisture_percent",
		"netDryQty": "net_dry_qty",
		"germinationPercent": "germination_percent",
		"geneticPurityPercent": "genetic_purity_percent",
		"vigorPercent": "vigor_percent",
		"undersizePercent": "undersize_percent",
		"rejectPercent": "reject_percent",
		"disposition": "disposition",
		"eligibleAreaHectares": "eligible_area_hectares",
		"provisionalYieldKgPerHectare": "provisional_yield_kg_per_hectare",
		"provisionalPricingBand": "provisional_pricing_band",
		"provisionalPriceBasis": "provisional_price_basis",
		"provisionalPayableValue": "provisional_payable_value",
		"potentialBonusAmount": "potential_bonus_amount",
		"bonusStatus": "bonus_status",
	},
	"Crop Cycle Stage": {
		"stageId": "stage_id",
		"stageCode": "stage_code",
		"cropId": "crop",
		"stageName": "stage_name",
		"orderIndex": "order_index",
		"durationDays": "duration_days",
	},
	"Plot Crop Assignment": {
		"assignmentId": "assignment_id",
		"plotId": "plot",
		"cropCycleId": "crop_cycle",
		"seasonId": "season",
	},
	"Field Visit": {
		"visitId": "visit_id",
		"plotId": "plot",
		"cropCycleId": "crop_cycle",
		"stageId": "stage",
		"visitTypeId": "visit_type",
		"gpsLat": "gps_lat",
		"gpsLng": "gps_lng",
		"scheduledDate": "scheduled_date",
		"fieldTripId": "field_trip",
		"visitedBy": "visited_by",
		"gpsAccuracyM": "gps_accuracy_m",
		"actualStart": "actual_start",
		"actualEnd": "actual_end",
		"positioningExceptionReason": "positioning_exception_reason",
	},
	"Field Trip": {
		"externalId": "external_id", "fieldOfficer": "field_officer",
		"startDatetime": "start_datetime", "endDatetime": "end_datetime",
		"transportMethod": "transport_method", "openingOdometer": "opening_odometer",
		"closingOdometer": "closing_odometer", "tripSummary": "trip_summary",
	},
	"Inspection": {
		"inspectionId": "inspection_id",
		"inspectionTemplateId": "inspection_template",
		"templateVersion": "template_version",
		"configurationSnapshot": "configuration_snapshot",
		"inspectionType": "inspection_type",
		"cropCycleId": "crop_cycle",
		"productionContractId": "production_contract",
		"plotId": "plot",
		"outgrowerId": "outgrower",
		"cropId": "crop",
		"seasonId": "season",
		"productionCategory": "production_category",
		"scheduledDate": "scheduled_date",
		"startedAt": "started_at",
		"completedAt": "completed_at",
		"stageId": "stage",
		"fieldVisitId": "field_visit",
		"assignedTo": "assigned_to",
		"requiredTakeCount": "required_take_count",
		"completedTakeCount": "completed_take_count",
		"cumulativeTotalPlants": "cumulative_total_plants",
		"controlsCompleted": "controls_completed",
		"farmerCompliancePercent": "farmer_compliance_percent",
		"farmerComplianceStatus": "farmer_compliance_status",
		"supervisorCompliancePercent": "supervisor_compliance_percent",
		"supervisorComplianceStatus": "supervisor_compliance_status",
		"fieldCertificationStatus": "field_certification_status",
		"targetTakeSpacingM": "target_take_spacing_m",
		"minimumTakeSpacingStandardM": "minimum_take_spacing_standard_m",
		"maximumTakeSpacingStandardM": "maximum_take_spacing_standard_m",
		"averageTakeSpacingM": "average_take_spacing_m",
		"medianTakeSpacingM": "median_take_spacing_m",
		"minimumObservedTakeSpacingM": "minimum_observed_take_spacing_m",
		"maximumObservedTakeSpacingM": "maximum_observed_take_spacing_m",
		"spacingPairCount": "spacing_pair_count",
		"spacingCompliantCount": "spacing_compliant_count",
		"spacingCompliancePercent": "spacing_compliance_percent",
		"averageGpsAccuracyM": "average_gps_accuracy_m",
		"worstGpsAccuracyM": "worst_gps_accuracy_m",
		"lowAccuracyTakeCount": "low_accuracy_take_count",
		"positioningOverrideCount": "positioning_override_count",
		"totalTakePathDistanceM": "total_take_path_distance_m",
		"takesOutsidePlot": "takes_outside_plot",
		"inspectionQualityScore": "inspection_quality_score",
		"inspectionMapGeojson": "inspection_map_geojson",
	},
	"Inspection Take": {
		"takeNumber": "take_number",
		"totalPlantsCounted": "total_plants_counted",
		"gpsAccuracyMeters": "gps_accuracy_meters",
		"gpsQualityStatus": "gps_quality_status",
		"locationSampleCount": "location_sample_count",
		"locationCaptureDurationSeconds": "location_capture_duration_seconds",
		"locationSource": "location_source",
		"capturedAt": "captured_at",
		"capturedBy": "captured_by",
		"attributeCount": "attribute_count",
		"takeStatus": "take_status",
		"insidePlotBoundary": "inside_plot_boundary",
		"distanceFromPreviousTakeM": "distance_from_previous_take_m",
		"spacingStatus": "spacing_status",
		"positioningOverride": "positioning_override",
		"positioningOverrideReason": "positioning_override_reason",
		"positioningOverrideBy": "positioning_override_by",
	},
	"Inspection Take Result": {
		"takeNumber": "take_number",
		"observedCount": "observed_count",
		"measuredValue": "measured_value",
		"textValue": "text_value",
		"resultStatus": "result_status",
		"correctiveActionRequired": "corrective_action_required",
	},
	"Inspection Take Evidence": {
		"evidenceId": "external_id",
		"takeNumber": "take_number",
		"parameterId": "parameter",
		"fileUrl": "file",
		"fileType": "file_type",
		"capturedAt": "captured_at",
		"capturedBy": "captured_by",
		"fileHash": "file_hash",
	},
	"Inspection Result": {
		"aggregationMethod": "aggregation_method",
		"observationCount": "observation_count",
		"passedCount": "passed_count",
		"failedCount": "failed_count",
		"passPercent": "pass_percent",
		"cumulativeObservedCount": "cumulative_observed_count",
		"cumulativeTotalPlants": "cumulative_total_plants",
		"incidencePercent": "incidence_percent",
		"measuredValue": "measured_value",
		"textValue": "text_value",
		"resultStatus": "result_status",
		"correctiveActionRequired": "corrective_action_required",
		"dueDate": "due_date",
	},
	"Inspection Observation": {
		"measuredValue": "measured_value",
		"textValue": "text_value",
		"resultStatus": "result_status",
		"correctiveActionRequired": "corrective_action_required",
		"capturedBy": "captured_by",
		"capturedAt": "captured_at",
	},
	"Inspection Template": {
		"templateName": "template_name",
		"inspectionType": "inspection_type",
		"cropStage": "crop_stage",
		"dueDaysFromPlanting": "due_days_from_planting",
		"dueWindowEndDays": "due_window_end_days",
		"countsPerHectare": "counts_per_hectare",
		"defaultAssignedTo": "default_assigned_to",
		"configurationVersion": "configuration_version",
		"lifecycleStatus": "lifecycle_status",
		"supersedesTemplate": "supersedes_template",
		"effectiveFrom": "effective_from",
		"effectiveTo": "effective_to",
	},
	"Inspection Parameter": {
		"parameterName": "parameter_name",
		"parameterCode": "parameter_code",
		"parameterGroup": "parameter_group",
		"dataType": "data_type",
		"selectOptions": "select_options",
		"appliesTo": "applies_to",
		"measurementScope": "measurement_scope",
		"calculationMethod": "calculation_method",
		"denominatorBasis": "denominator_basis",
		"requiresTakeCounts": "requires_take_counts",
		"inspectionAttribute": "inspection_attribute",
		"evidencePolicy": "evidence_policy",
		"minimumEvidenceFiles": "minimum_evidence_files",
		"maximumEvidenceFiles": "maximum_evidence_files",
		"allowMultipleFiles": "allow_multiple_files",
		"decimalPrecision": "decimal_precision",
		"active": "active",
	},
	"Inspection Standard": {
		"inspectionTemplateId": "inspection_template",
		"productionCategory": "production_category",
		"comparisonRule": "comparison_rule",
		"aggregationMethod": "aggregation_method",
		"minimumValue": "minimum_value",
		"maximumValue": "maximum_value",
		"expectedText": "expected_text",
		"goodLabel": "good_label",
		"poorLabel": "poor_label",
		"autoRejectOnFail": "auto_reject_on_fail",
		"correctiveActionOnFail": "corrective_action_on_fail",
		"standardNotes": "standard_notes",
		"sectionLabel": "section_label",
		"displayOrder": "display_order",
	},
	"Inspection Template Parameter": {
		"inspectionTemplateId": "parent",
		"inspectionAttribute": "inspection_attribute",
		"sectionLabel": "section_label",
		"displayOrder": "display_order",
		"productionCategory": "production_category",
		"seedClass": "seed_class",
		"comparisonRule": "comparison_rule",
		"minimumValue": "minimum_value",
		"maximumValue": "maximum_value",
		"expectedText": "expected_text",
		"goodLabel": "good_label",
		"poorLabel": "poor_label",
		"aggregationMethod": "aggregation_method",
		"autoRejectOnFail": "auto_reject_on_fail",
		"correctiveActionOnFail": "corrective_action_on_fail",
		"standardNotes": "standard_notes",
	},
	"Inspection Template Applicability": {
		"inspectionTemplateId": "parent",
		"productionCategory": "production_category",
		"seedClass": "seed_class",
		"effectiveFrom": "effective_from",
		"effectiveTo": "effective_to",
	},
	"Inspection Attribute": {
		"attributeName": "attribute_name",
		"attributeCode": "attribute_code",
		"attributeGroup": "attribute_group",
		"attributeType": "attribute_type",
		"active": "active",
	},
	"Agronomy Activity Template": {
		"activityName": "activity_name",
		"cropRecipeId": "crop_recipe",
		"stageName": "stage_name",
		"dayOffsetFromPlanting": "day_offset_from_planting",
		"dayOffsetEnd": "day_offset_end",
		"responsibleParty": "responsible_party",
		"inspectionRelated": "inspection_related",
		"evidenceRequired": "evidence_required",
	},
	"Agronomy Report Template": {
		"reportName": "report_name",
		"reportNumber": "report_number",
		"stageName": "stage_name",
		"windowStartDay": "window_start_day",
		"windowEndDay": "window_end_day",
		"templateVersion": "template_version",
		"overallPassThresholdPercent": "overall_pass_threshold_percent",
		"criticalFailureOverride": "critical_failure_override",
	},
	"Agronomy Report Parameter": {
		"parameterCode": "parameter_code",
		"parameterLabel": "parameter_label",
		"sectionName": "section_name",
		"dataType": "data_type",
		"evaluationMode": "evaluation_mode",
		"comparisonRule": "comparison_rule",
		"minimumValue": "minimum_value",
		"maximumValue": "maximum_value",
		"expectedValue": "expected_value",
		"severity": "severity",
		"weight": "weight",
		"allowNotApplicable": "allow_not_applicable",
		"responsibleParty": "responsible_party",
		"correctiveActionOnFail": "corrective_action_on_fail",
		"failureAction": "failure_action",
		"correctiveActionDueDays": "corrective_action_due_days",
	},
	"Agronomy Report": {
		"reportTemplateId": "report_template",
		"reportNumber": "report_number",
		"cropCycleId": "crop_cycle",
		"stageId": "stage",
		"fieldVisitId": "field_visit",
		"stageName": "stage_name",
		"productionContractId": "production_contract",
		"plotId": "plot",
		"outgrowerId": "outgrower",
		"assignedSupervisor": "assigned_supervisor",
		"windowStartDate": "window_start_date",
		"windowEndDate": "window_end_date",
		"reportDate": "report_date",
		"calendarWeek": "calendar_week",
		"plantingWeek": "planting_week",
		"gpsAccuracyMeters": "gps_accuracy_meters",
		"locationCapturedAt": "location_captured_at",
		"insidePlotBoundary": "inside_plot_boundary",
		"locationBoundaryOverride": "location_boundary_override",
		"locationBoundaryOverrideReason": "location_boundary_override_reason",
		"locationBoundaryOverrideBy": "location_boundary_override_by",
		"locationBoundaryOverrideAt": "location_boundary_override_at",
		"overallResult": "overall_result",
		"passPercentage": "pass_percentage",
		"evaluatedParameterCount": "evaluated_parameter_count",
		"passedParameterCount": "passed_parameter_count",
		"failedParameterCount": "failed_parameter_count",
		"criticalFailureCount": "critical_failure_count",
		"evaluatedAt": "evaluated_at",
		"templateVersion": "template_version",
		"overallPassThresholdPercent": "overall_pass_threshold_percent",
		"criticalFailureOverride": "critical_failure_override",
		"fieldNotes": "field_notes",
		"correctiveActionRequired": "corrective_action_required",
		"correctiveAction": "corrective_action",
		"correctiveActionDueDate": "corrective_action_due_date",
		"submittedBy": "submitted_by",
		"submittedAt": "submitted_at",
		"stageLockOverrideBy": "stage_lock_override_by",
		"stageLockOverrideAt": "stage_lock_override_at",
		"stageLockOverrideReason": "stage_lock_override_reason",
	},
	"Agronomy Report Result": {
		"parameterCode": "parameter_code",
		"parameterLabel": "parameter_label",
		"sectionName": "section_name",
		"dataType": "data_type",
		"responsibleParty": "responsible_party",
		"numericValue": "numeric_value",
		"valueCaptured": "value_captured",
		"textValue": "text_value",
		"dateValue": "date_value",
		"options": "options",
		"templateVersion": "template_version",
		"evaluationMode": "evaluation_mode",
		"comparisonRule": "comparison_rule",
		"minimumValue": "minimum_value",
		"maximumValue": "maximum_value",
		"expectedValue": "expected_value",
		"severity": "severity",
		"weight": "weight",
		"allowNotApplicable": "allow_not_applicable",
		"correctiveActionOnFail": "corrective_action_on_fail",
		"failureAction": "failure_action",
		"correctiveActionDueDays": "corrective_action_due_days",
		"resultStatus": "result_status",
		"evaluationMessage": "evaluation_message",
	},
	"Field Corrective Action": {
		"sourceType": "source_type",
		"inspectionId": "inspection",
		"verificationAssignedTo": "verification_assigned_to",
		"verificationNotes": "verification_notes",
		"respondedOn": "responded_on",
		"sourceName": "source_name",
		"sourceParameter": "source_parameter",
		"agronomyReportId": "agronomy_report",
		"cropCycleId": "crop_cycle",
		"plotId": "plot",
		"outgrowerId": "outgrower",
		"responsibleParty": "responsible_party",
		"assignedTo": "assigned_to",
		"dueDate": "due_date",
		"resolutionNotes": "resolution_notes",
		"closedOn": "closed_on",
	},
	"Stage Activity": {
		"activityId": "activity_id",
		"cropCycleId": "crop_cycle",
		"stageId": "stage",
		"visitId": "visit",
		"assignedTo": "assigned_to",
		"activityDate": "activity_date",
		"dueDate": "due_date",
		"durationHours": "duration_hours",
		"activityTemplateId": "activity_template",
		"completionNotes": "completion_notes",
		"completedOn": "completed_on",
		"stageLockOverrideBy": "stage_lock_override_by",
		"stageLockOverrideAt": "stage_lock_override_at",
		"stageLockOverrideReason": "stage_lock_override_reason",
	},
	"Stage Input Request": {
		"requestId": "request_id",
		"cropCycleId": "crop_cycle",
		"stageId": "stage",
		"inputType": "input_type",
		"fieldVisitId": "field_visit",
		"externalId": "external_id",
		"quantity": "quantity",
		"requestedDate": "requested_date",
		"requestDate": "request_date",
		"requiredBy": "required_by",
		"outgrowerId": "outgrower",
		"supplierId": "supplier",
		"sourceWarehouseId": "source_warehouse",
		"materialRequestId": "material_request",
		"totalRequestedValue": "total_requested_value",
		"totalApprovedValue": "total_approved_value",
	},
	"Stage Input Request Item": {
		"recipeInputItemId": "recipe_input_item",
		"itemCode": "item_code",
		"itemName": "item_name",
		"requestedQty": "requested_qty",
		"approvedQty": "approved_qty",
		"conversionFactor": "conversion_factor",
		"stockUom": "stock_uom",
		"requestedStockQty": "requested_stock_qty",
		"approvedStockQty": "approved_stock_qty",
		"issuedQty": "issued_qty",
		"issuedStockQty": "issued_stock_qty",
		"remainingQty": "remaining_qty",
		"remainingStockQty": "remaining_stock_qty",
		"sourceWarehouseId": "source_warehouse",
		"estimatedRate": "estimated_rate",
		"estimatedAmount": "estimated_amount",
		"recoveryPolicy": "recovery_policy",
		"recoverablePercent": "recoverable_percent",
		"recoveryRateBasis": "recovery_rate_basis",
		"contractRecoveryRate": "contract_recovery_rate",
	},
	"Stage Input Dispatch": {
		"dispatchId": "dispatch_id",
		"cropCycleId": "crop_cycle",
		"stageId": "stage",
		"inputType": "input_type",
		"quantity": "quantity",
		"dispatchDate": "dispatch_date",
		"requestId": "request_id",
		"inputRequestId": "input_request",
		"inputRequestItemId": "input_request_item",
		"stockEntryId": "stock_entry",
		"stockEntryDetailId": "stock_entry_detail",
		"itemCode": "item_code",
		"quantityDispatched": "quantity_dispatched",
		"receivedBy": "received_by",
		"receivedByName": "received_by_name",
		"receivedAt": "received_at",
		"gpsAccuracyMeters": "gps_accuracy_meters",
		"gpsQualityStatus": "gps_quality_status",
		"geolocation": "geolocation",
		"deliveryPhoto": "delivery_photo",
		"evidenceFile": "evidence_file",
		"workflowStatus": "workflow_status",
		"receiverSignature": "receiver_signature",
	},
	"Crop Cycle Advance Request": {
		"cropCycleId": "crop_cycle",
		"outgrowerId": "outgrower",
		"supplierId": "supplier",
		"companyId": "company",
		"purchaseOrderId": "purchase_order",
		"requestDate": "request_date",
		"requestedAmount": "requested_amount",
		"approvedAmount": "approved_amount",
		"paidAmount": "paid_amount",
		"paymentDate": "payment_date",
		"paymentEntryId": "payment_entry",
		"exposureLimit": "exposure_limit",
		"currentExposure": "current_exposure",
		"availableCapacity": "available_capacity",
	},
	"Crop Cycle Settlement": {
		"cropCycleId": "crop_cycle",
		"outgrowerId": "outgrower",
		"supplierId": "supplier",
		"purchaseOrderId": "purchase_order",
		"purchaseInvoiceId": "purchase_invoice",
		"postingDate": "posting_date",
		"grossHarvestValue": "gross_harvest_value",
		"stockRecoveryDue": "stock_recovery_due",
		"stockRecoveryToDeduct": "stock_recovery_to_deduct",
		"cashAdvanceAvailable": "cash_advance_available",
		"cashAdvanceToAllocate": "cash_advance_to_allocate",
		"invoiceTotal": "invoice_total",
		"netPayable": "net_payable",
		"unrecoveredBalance": "unrecovered_balance",
	},
	"Crop Recipe": {
		"recipeId": "recipe_id",
		"cropId": "crop",
		"recipeName": "recipe_name",
	},
	"Recipe Stage": {
		"name": "stage_name",
		"orderIndex": "order_index",
		"durationDays": "duration_days",
	},
	"Recipe Input Item": {
		"type": "input_type",
		"name": "input_name",
		"quantityPerHectare": "quantity_per_hectare",
	},
	"Visit Type": {
		"visitTypeId": "visit_type_id",
		"name": "type_name",
	},
	"Region": {
		"name": "region_name",
	},
	"UOM": {
		"unitName": "uom_name",
	},
	"Inspection Attribute": {
		"attributeName": "attribute_name",
	},
	"Attendance": {
		"attendanceId": "attendance_id",
		"date": "attendance_date",
		"checkInTime": "check_in_time",
		"checkOutTime": "check_out_time",
		"lateEntry": "late_entry",
		"earlyExit": "early_exit",
		"totalDistanceKm": "total_distance_km",
		"checkInLat": "check_in_lat",
		"checkInLng": "check_in_lng",
		"checkOutLat": "check_out_lat",
		"checkOutLng": "check_out_lng",
	},
	"Employee Checkin": {
		"checkinId": "checkin_id",
		"userId": "user_id",
		"userEmail": "user_email",
		"latitude": "latitude",
		"longitude": "longitude",
		"deviceId": "device_id",
		"logType": "log_type",
		"time": "time",
	},
	"Leave Application": {
		"applicationId": "external_id",
		"userId": "employee",
		"leaveType": "leave_type",
		"fromDate": "from_date",
		"toDate": "to_date",
		"isHalfDay": "half_day",
		"approverEmail": "approver_email",
		"approverName": "approver_name",
		"status": "status",
		"attachments": "attachments_json",
	},
	"Employee Advance": {
		"advanceId": "external_id",
		"userId": "employee",
		"postingDate": "posting_date",
		"purpose": "purpose",
		"amount": "advance_amount",
		"currency": "currency",
		"exchangeRate": "exchange_rate",
		"advanceAccount": "advance_account",
		"modeOfPayment": "mode_of_payment",
		"repayFromSalary": "repay_from_salary",
		"status": "status",
		"attachments": "attachments_json",
	},
	"Expense Claim": {
		"expenseId": "external_id",
		"userId": "employee",
		"dateSubmitted": "date_submitted",
		"amount": "total_claimed_amount",
		"category": "category",
		"status": "status",
		"fieldTripId": "custom_field_trip",
		"fieldVisitId": "custom_field_visit",
	},
	"Plot Vertex": {
		"lat": "latitude",
		"lng": "longitude",
		"orderIndex": "order_index",
	},
	"Visit Photo": {
		"file": "photo",
	},
	"Plot Photo": {
		"file": "file",
	},
}


LEGACY_AREA_MOBILE_FIELDS = {
	"Farm Plot": {"areaAcres": ("areaHectares", 0.40468564224)},
	"Outgrower Production Contract": {
		"contractedAreaAcres": ("contractedAreaHectares", 0.40468564224),
		"quotaKgPerAcre": ("quotaKgPerHectare", 2.47105381467),
	},
	"Crop Production Lot": {
		"areaAcres": ("areaHectares", 0.40468564224),
		"acceptedAreaAcres": ("acceptedAreaHectares", 0.40468564224),
		"rejectedAreaAcres": ("rejectedAreaHectares", 0.40468564224),
	},
	"Seed Harvest Quality Assessment": {
		"eligibleAreaAcres": ("eligibleAreaHectares", 0.40468564224),
		"provisionalYieldKgPerAcre": (
			"provisionalYieldKgPerHectare",
			2.47105381467,
		),
	},
}


def _apply_legacy_area_payload(doctype, payload):
	for old_key, (new_key, factor) in LEGACY_AREA_MOBILE_FIELDS.get(doctype, {}).items():
		if new_key not in payload and payload.get(old_key) is not None:
			payload[new_key] = flt(payload.get(old_key)) * factor


def _apply_legacy_area_response(doctype, result):
	"""Outbound mirror of _apply_legacy_area_payload: some client models
	(Plot.areaAcres in particular) only ever read the *Acres field and have
	no fallback to the canonical *Hectares mobile field, so a pull-only
	client would otherwise cache these as permanently null."""
	for old_key, (new_key, factor) in LEGACY_AREA_MOBILE_FIELDS.get(doctype, {}).items():
		if old_key not in result and result.get(new_key) is not None:
			result[old_key] = flt(result.get(new_key)) / factor


def _map_mobile_to_doc(doctype, payload):
	payload = dict(payload or {})
	if doctype == "Outgrower":
		payload = _normalize_outgrower_payload(payload)
	_apply_legacy_area_payload(doctype, payload)

	mapping = MOBILE_FIELD_MAP.get(doctype, {})
	result = {}
	for key, value in (payload or {}).items():
		if key in ("doctype", "name", "owner", "creation", "modified", "modified_by", "docstatus"):
			continue
		# ignore client-only fields
		if key in ("synced",):
			continue
		if key == "createdAt":
			result["creation"] = value
			continue
		if key == "updatedAt":
			result["modified"] = value
			continue
		if key == "photos" and doctype == "Field Visit":
			# child table photos: list of strings
			result["photos"] = [{"photo": p} for p in value or []]
			continue
		if key == "photos" and doctype == "Farm Plot":
			result["photos"] = [{"file": p} for p in value or []]
			continue
		if key == "polygon" and doctype == "Farm Plot":
			result["polygon"] = [
				{
					MOBILE_FIELD_MAP["Plot Vertex"].get("lat", "latitude"): v.get("lat"),
					MOBILE_FIELD_MAP["Plot Vertex"].get("lng", "longitude"): v.get("lng"),
					MOBILE_FIELD_MAP["Plot Vertex"].get("orderIndex", "order_index"): v.get("orderIndex", idx + 1),
				}
				for idx, v in enumerate(value or [])
			]
			continue
		if key == "stages" and doctype == "Crop Recipe":
			result["stages"] = []
			for stage in value or []:
				stage_doc = {
					"stage_name": stage.get("name"),
					"order_index": stage.get("orderIndex"),
					"duration_days": stage.get("durationDays"),
				}
				inputs = []
				for inp in (
					stage.get("inputsPerHectare") or stage.get("inputsPerAcre") or []
				):
					inputs.append({
						"input_type": inp.get("type"),
						"input_name": inp.get("name"),
						"quantity_per_hectare": (
							inp.get("quantityPerHectare")
							if inp.get("quantityPerHectare") is not None
							else flt(inp.get("quantityPerAcre")) * 2.47105381467
						),
						"unit": inp.get("unit"),
					})
				stage_doc["inputs"] = inputs
			result["stages"].append(stage_doc)
			continue
		if key == "parentSeeds" and doctype == "Outgrower Production Contract":
			result["parent_seed_items"] = [
				_map_mobile_child_to_doc("Contract Parent Seed Item", row)
				for row in value or []
			]
			continue
		if key == "takes" and doctype == "Inspection":
			result["takes"] = []
			nested_readings = []
			for index, row in enumerate(value or [], start=1):
				take = _map_mobile_child_to_doc("Inspection Take", row)
				take_number = take.get("take_number") or index
				take["take_number"] = take_number
				result["takes"].append(take)
				for reading in row.get("readings") or row.get("attributes") or row.get("results") or []:
					mapped = _map_mobile_child_to_doc("Inspection Take Result", reading)
					mapped["take_number"] = mapped.get("take_number") or take_number
					nested_readings.append(mapped)
			if nested_readings:
				result.setdefault("take_results", []).extend(nested_readings)
			continue
		if key in ("takeResults", "take_results") and doctype == "Inspection":
			result.setdefault("take_results", []).extend(
				[_map_mobile_child_to_doc("Inspection Take Result", row) for row in value or []]
			)
			continue
		if key in ("takeEvidence", "take_evidence") and doctype == "Inspection":
			result["take_evidence"] = [
				_map_mobile_child_to_doc("Inspection Take Evidence", row) for row in value or []
			]
			continue
		if key in ("inspectionObservations", "inspection_observations") and doctype == "Inspection":
			result["inspection_observations"] = [
				_map_mobile_child_to_doc("Inspection Observation", row) for row in value or []
			]
			continue
		if key == "results" and doctype == "Inspection":
			# Inspection Results are server-generated aggregates. Legacy result
			# payloads are accepted only when they identify their Inspection Take.
			for row in value or []:
				if row.get("takeNumber") or row.get("take_number"):
					result.setdefault("take_results", []).append(
						_map_mobile_child_to_doc("Inspection Take Result", row)
					)
			continue
		if key == "items" and doctype == "Stage Input Request":
			result["items"] = [
				_map_mobile_child_to_doc("Stage Input Request Item", row)
				for row in value or []
			]
			continue
		if key == "results" and doctype == "Agronomy Report":
			result["results"] = [
				_map_mobile_child_to_doc("Agronomy Report Result", row)
				for row in value or []
			]
			continue

		fieldname = mapping.get(key, key)
		result[fieldname] = value

	# normalize required fields for existing doctypes
	if doctype == "Stage Input Request":
		if result.get("input_type") and not result.get("input_name"):
			result["input_name"] = result.get("input_type")
		if result.get("quantity") is not None and not result.get("quantity_needed"):
			result["quantity_needed"] = result.get("quantity")
		if result.get("requested_date") and not result.get("request_date"):
			result["request_date"] = result.get("requested_date")

	if doctype == "Stage Input Dispatch":
		if result.get("input_type") and not result.get("input_name"):
			result["input_name"] = result.get("input_type")
		if result.get("quantity") is not None and not result.get("quantity_dispatched"):
			result["quantity_dispatched"] = result.get("quantity")
		if result.get("request_id") and not result.get("input_request"):
			result["input_request"] = result.get("request_id")

	if doctype == "Field Visit" and result.get("status") and not result.get("visit_status"):
		result["visit_status"] = "Submitted" if result.get("status") == "completed" else "Draft"

	result = _resolve_employee_fields(doctype, payload, result)
	return _filter_fields(doctype, result)


def _map_mobile_child_to_doc(doctype, payload):
	mapping = MOBILE_FIELD_MAP.get(doctype, {})
	result = {}
	for key, value in (payload or {}).items():
		if key in ("doctype", "name", "owner", "creation", "modified", "modified_by", "docstatus"):
			continue
		result[mapping.get(key, key)] = value
	return _filter_fields(doctype, result)


def _map_doc_to_mobile(doctype, doc_dict):
	mapping = MOBILE_FIELD_MAP.get(doctype, {})
	reverse = {v: k for k, v in mapping.items()}
	result = {}
	for key, value in (doc_dict or {}).items():
		if key in ("doctype", "owner", "modified_by", "docstatus", "idx", "parent", "parenttype", "parentfield") and key not in reverse:
			continue
		if key == "creation":
			result["createdAt"] = value
			continue
		if key == "modified":
			result["updatedAt"] = value
			continue
		if key == "photos" and doctype == "Field Visit":
			result["photos"] = [p.get("photo") for p in (value or [])]
			continue
		if key == "photos" and doctype == "Farm Plot":
			result["photos"] = [p.get("file") or p.get("url") for p in (value or [])]
			continue
		if key == "polygon" and doctype == "Farm Plot":
			result["polygon"] = [
				{
					"lat": v.get("latitude"),
					"lng": v.get("longitude"),
					"orderIndex": v.get("order_index"),
				}
				for v in (value or [])
			]
			continue
		if key == "stages" and doctype == "Crop Recipe":
			stages = []
			for s in value or []:
				stage = {
					"name": s.get("stage_name"),
					"orderIndex": s.get("order_index"),
					"durationDays": s.get("duration_days"),
				}
				inputs = []
				stage_inputs = [
					row for row in doc_dict.get("inputs", []) or []
					if (row.get("recipe_stage") in (s.get("stage_name"), s.get("name"))
						if row.get("recipe_stage") else
						s.get("order_index") is not None and
						str(row.get("stage_index")) == str(s.get("order_index")))
				]
				for inp in stage_inputs or s.get("inputs", []) or []:
					inputs.append({
						"type": inp.get("input_type"),
						"name": inp.get("input_name"),
						"quantityPerHectare": inp.get("quantity_per_hectare"),
						"unit": inp.get("unit"),
					})
				stage["inputsPerHectare"] = inputs
				stages.append(stage)
			result["stages"] = stages
			continue
		if key == "parent_seed_items" and doctype == "Outgrower Production Contract":
			result["parentSeeds"] = [
				_map_doc_to_mobile("Contract Parent Seed Item", row)
				for row in value or []
			]
			continue
		if key == "takes" and doctype == "Inspection":
			result["takes"] = [_map_doc_to_mobile("Inspection Take", row) for row in value or []]
			continue
		if key == "take_results" and doctype == "Inspection":
			result["takeResults"] = [
				_map_doc_to_mobile("Inspection Take Result", row) for row in value or []
			]
			continue
		if key == "take_evidence" and doctype == "Inspection":
			result["takeEvidence"] = [
				_map_doc_to_mobile("Inspection Take Evidence", row) for row in value or []
			]
			continue
		if key == "inspection_observations" and doctype == "Inspection":
			result["inspectionObservations"] = [
				_map_doc_to_mobile("Inspection Observation", row) for row in value or []
			]
			continue
		if key == "results" and doctype == "Inspection":
			result["results"] = [_map_doc_to_mobile("Inspection Result", row) for row in value or []]
			continue
		if key == "items" and doctype == "Stage Input Request":
			result["items"] = [
				_map_doc_to_mobile("Stage Input Request Item", row)
				for row in value or []
			]
			continue
		if key == "results" and doctype == "Agronomy Report":
			result["results"] = [
				_map_doc_to_mobile("Agronomy Report Result", row) for row in value or []
			]
			continue
		if key == "parameters" and doctype == "Agronomy Report Template":
			result["parameters"] = [
				_map_doc_to_mobile("Agronomy Report Parameter", row) for row in value or []
			]
			continue

		result[reverse.get(key, key)] = value

	_apply_legacy_area_response(doctype, result)

	# ensure id fields returned
	if doctype in ID_FIELD_MAP and ID_FIELD_MAP[doctype] in doc_dict:
		mobile_id_field = _reverse_id_field_name(doctype)
		if mobile_id_field:
			result[mobile_id_field] = (
				doc_dict.get(ID_FIELD_MAP[doctype]) or doc_dict.get("name")
			)
	if doctype == "Leave Application":
		approver = doc_dict.get("leave_approver") or ""
		result["approverEmail"] = result.get("approverEmail") or approver
		result["approverName"] = (
			result.get("approverName") or (get_fullname(approver) if approver else "")
		)
	if doctype == "Expense Claim":
		expenses = doc_dict.get("expenses") or []
		first_expense = expenses[0] if expenses else {}
		result["dateSubmitted"] = (
			result.get("dateSubmitted") or doc_dict.get("posting_date")
		)
		result["amount"] = (
			result.get("amount") or doc_dict.get("total_claimed_amount") or 0
		)
		result["category"] = (
			result.get("category") or first_expense.get("expense_type") or ""
		)
		result["description"] = (
			result.get("description") or first_expense.get("description")
		)
	if doctype == "Outgrower":
		_enrich_outgrower_aliases(result)
	if doctype == "Inspection":
		readings_by_take = {}
		for reading in result.get("takeResults", []):
			readings_by_take.setdefault(reading.get("takeNumber"), []).append(reading)
		for take in result.get("takes", []):
			take["readings"] = readings_by_take.get(take.get("takeNumber"), [])
	if doctype == "Stage Input Request Item" and doc_dict.get("name"):
		result["inputRequestItemId"] = doc_dict.get("name")
	return _attach_user_full_names(doctype, doc_dict, result)


_user_full_name_cache = {}


def _attach_user_full_names(doctype, source, result=None):
	"""Add display-only names for authorized User links without replacing IDs."""
	result = dict(result if result is not None else source or {})
	try:
		meta = _get_meta(doctype)
	except Exception:
		return result
	reverse = {value: key for key, value in MOBILE_FIELD_MAP.get(doctype, {}).items()}
	for field in meta.fields:
		if field.fieldtype != "Link" or field.options != "User":
			continue
		user_id = (source or {}).get(field.fieldname)
		if not user_id:
			continue
		if user_id not in _user_full_name_cache:
			_user_full_name_cache[user_id] = get_fullname(user_id) or user_id
		full_name = _user_full_name_cache[user_id]
		result[f"{field.fieldname}_full_name"] = full_name
		mobile_field = reverse.get(field.fieldname)
		if mobile_field:
			result[f"{mobile_field}FullName"] = full_name
	return result


def _reverse_id_field_name(doctype):
	for mobile_field, frappe_field in MOBILE_FIELD_MAP.get(doctype, {}).items():
		if frappe_field == ID_FIELD_MAP.get(doctype):
			return mobile_field
	return None


def _resolve_doctype(store_or_doctype, strict=False):
	if store_or_doctype in STORE_TO_DOCTYPE:
		return STORE_TO_DOCTYPE.get(store_or_doctype)
	if store_or_doctype in set(STORE_TO_DOCTYPE.values()):
		return store_or_doctype
	if isinstance(store_or_doctype, str):
		key = store_or_doctype.lower()
		if key in STORE_TO_DOCTYPE:
			return STORE_TO_DOCTYPE.get(key)
	if strict:
		frappe.throw(_("Unsupported mobile data type: {0}").format(store_or_doctype))
	return store_or_doctype


def _mobile_roles(user=None):
	user = user or frappe.session.user
	return set(frappe.get_roles(user))


def _mobile_has_management_access(roles=None):
	roles = roles or _mobile_roles()
	return bool(
		{"System Manager", OUTGROWER_MANAGER_ROLE, QUALITY_MANAGER_ROLE}.intersection(roles)
	) or frappe.session.user == "Administrator"


def _mobile_allowed_doctypes(mode="read"):
	roles = _mobile_roles()
	if _mobile_has_management_access(roles):
		return set(STORE_TO_DOCTYPE.values())
	allowed = set(MOBILE_REFERENCE_DOCTYPES) if mode == "read" else set()
	if mode == "read" and frappe.session.user != "Guest":
		allowed.update({"Attendance", "Employee Checkin"})
	if frappe.session.user != "Guest":
		allowed.update(MOBILE_HR_SELF_SERVICE_DOCTYPES)
	role_map = MOBILE_ROLE_READ if mode == "read" else MOBILE_ROLE_WRITE
	for role, doctypes in role_map.items():
		if role in roles:
			allowed.update(doctypes)
	return allowed


def _require_mobile_doctype(doctype, mode="read"):
	if doctype not in _mobile_allowed_doctypes(mode):
		frappe.throw(
			_("You are not permitted to {0} {1} from the mobile client.").format(
				mode, doctype
			),
			frappe.PermissionError,
		)


def _mobile_scope_names(doctype, user=None):
	if doctype in {"Attendance", "Employee Checkin"}:
		employees = _get_attendance_employee_ids({})
		return set(frappe.get_all(doctype, filters={"employee": ["in", employees]}, pluck="name")) if employees else set()
	if doctype in MOBILE_HR_SELF_SERVICE_DOCTYPES:
		employees = _get_attendance_employee_ids({})
		return set(
			frappe.get_all(doctype, filters={"employee": ["in", employees]}, pluck="name")
		) if employees else set()
	user = user or frappe.session.user
	roles = _mobile_roles(user)
	if _mobile_has_management_access(roles) or doctype in MOBILE_REFERENCE_DOCTYPES:
		return None

	supervisor = OUTGROWER_SUPERVISOR_ROLE in roles
	inspector = QUALITY_INSPECTOR_ROLE in roles
	outgrowers = set()
	cycles = set()

	if supervisor:
		outgrowers.update(
			frappe.get_all(
				"Outgrower", filters={"assigned_supervisor": user}, pluck="name"
			)
		)
	if inspector:
		inspections = frappe.get_all(
			"Inspection",
			filters={"assigned_to": user},
			fields=["name", "outgrower", "crop_cycle"],
		)
		outgrowers.update(row.outgrower for row in inspections if row.outgrower)
		cycles.update(row.crop_cycle for row in inspections if row.crop_cycle)

	plots = set(
		frappe.get_all(
			"Farm Plot",
			filters={"outgrower": ["in", list(outgrowers)]},
			pluck="name",
		)
	) if outgrowers else set()
	cycles.update(
		frappe.get_all(
			"Crop Cycle", filters={"plot": ["in", list(plots)]}, pluck="name"
		)
		if plots
		else []
	)

	if doctype == "Outgrower":
		return outgrowers
	if doctype == "Farm Plot":
		return plots
	if doctype in ("Crop Cycle", "Outgrower Production Contract"):
		if doctype == "Crop Cycle":
			return cycles
		return set(
			frappe.get_all(
				doctype, filters={"linked_crop_cycle": ["in", list(cycles)]}, pluck="name"
			)
		) if cycles else set()
	if doctype == "Inspection":
		return set(
			frappe.get_all(
				doctype, filters={"assigned_to": user}, pluck="name"
			)
		)
	if doctype == "Agronomy Report":
		return set(
			frappe.get_all(
				doctype, filters={"assigned_supervisor": user}, pluck="name"
			)
		)
	if doctype == "Stage Activity":
		return set(frappe.get_all(doctype, filters={"assigned_to": user}, pluck="name"))
	if doctype == "Field Visit":
		return set(
			frappe.get_all(doctype, filters={"plot": ["in", list(plots)]}, pluck="name")
		) if plots else set()
	if doctype == "Field Trip":
		return set(frappe.get_all(doctype, filters={"field_officer": user}, pluck="name"))
	if doctype == "Field Corrective Action":
		action_names = set()
		if supervisor:
			action_names.update(
				frappe.get_all(doctype, filters={"assigned_to": user}, pluck="name")
			)
		if inspector:
			action_names.update(
				frappe.get_all(
					doctype, filters={"verification_assigned_to": user}, pluck="name"
				)
			)
		return action_names
	if doctype in ("Stage Input Request", "Stage Input Dispatch", "Crop Production Lot"):
		return set(
			frappe.get_all(
				doctype, filters={"crop_cycle": ["in", list(cycles)]}, pluck="name"
			)
		) if cycles else set()
	if doctype == "Seed Harvest Quality Assessment":
		return set(frappe.get_all(doctype, filters={"inspected_by": user}, pluck="name"))
	if doctype == "Plot Crop Assignment":
		return set(
			frappe.get_all(
				doctype, filters={"crop_cycle": ["in", list(cycles)]}, pluck="name"
			)
		) if cycles else set()
	return set()


def _mobile_record_is_in_scope(doctype, name=None, values=None):
	names = _mobile_scope_names(doctype)
	if names is None:
		return True
	if name and name in names:
		return True
	values = values or {}
	user = frappe.session.user
	if doctype in MOBILE_HR_SELF_SERVICE_DOCTYPES:
		return values.get("employee") in set(_get_attendance_employee_ids({}))
	if doctype == "Outgrower":
		return values.get("assigned_supervisor") == user
	if doctype == "Farm Plot":
		return values.get("outgrower") in (_mobile_scope_names("Outgrower") or set())
	if doctype == "Stage Activity":
		return values.get("assigned_to") in (None, "", user) and values.get(
			"crop_cycle"
		) in (_mobile_scope_names("Crop Cycle") or set())
	if doctype == "Inspection":
		return values.get("assigned_to") == user and values.get("crop_cycle") in (
			_mobile_scope_names("Crop Cycle") or set()
		)
	if doctype == "Field Visit":
		cycle = values.get("crop_cycle")
		return values.get("plot") in (_mobile_scope_names("Farm Plot") or set()) and (
			not cycle or cycle in (_mobile_scope_names("Crop Cycle") or set())
		)
	if doctype == "Field Trip":
		return values.get("field_officer") in (None, "", user)
	if doctype == "Stage Input Request":
		return values.get("crop_cycle") in (_mobile_scope_names("Crop Cycle") or set())
	if doctype == "Seed Harvest Quality Assessment":
		return values.get("inspected_by") in (None, "", user) and values.get(
			"crop_cycle"
		) in (_mobile_scope_names("Crop Cycle") or set())
	return False


def _mobile_stage_order(doctype, name, values):
	"""(stage_order, current_order, stage) for a Stage Activity/Agronomy
	Report, or (None, None, None) if either can't be resolved. Shared by
	_mobile_stage_lock_error and mobile_unlock_stage_document so both agree
	on what "finished"/"current"/"upcoming" mean for a given record.
	"""
	values = values or {}
	crop_cycle = values.get("crop_cycle")
	stage = values.get("stage")
	if name and (not crop_cycle or not stage):
		existing = frappe.db.get_value(
			doctype, name, ["crop_cycle", "stage"], as_dict=True
		)
		if existing:
			crop_cycle = crop_cycle or existing.crop_cycle
			stage = stage or existing.stage
	if not crop_cycle or not stage:
		return None, None, stage

	current_stage = frappe.db.get_value("Crop Cycle", crop_cycle, "current_stage")
	if not current_stage:
		return None, None, stage

	stage_order = frappe.db.get_value("Crop Cycle Stage", stage, "order_index")
	current_order = frappe.db.get_value(
		"Crop Cycle Stage", current_stage, "order_index"
	)
	return stage_order, current_order, stage


def _mobile_stage_lock_error(doctype, name, values):
	"""None if the write may proceed; otherwise a user-facing reason string.

	Mirrors the Flutter client's StageAccessService: a Stage Activity or
	Agronomy Report may only be written while its Crop Cycle Stage is the
	cycle's current stage. The client already hides this in the UI, but
	nothing previously stopped a stale build or a direct API call from
	writing to any stage, so this is the actual data-integrity boundary.
	"""
	if doctype not in STAGE_LOCKED_DOCTYPES:
		return None

	stage_order, current_order, stage = _mobile_stage_order(doctype, name, values)
	if stage_order is None or current_order is None or stage_order == current_order:
		# Unresolved (missing links) or already the current stage: nothing to block here.
		return None

	if name:
		override_at = frappe.db.get_value(doctype, name, "stage_lock_override_at")
		if override_at:
			return None

	if stage_order < current_order:
		stage_end = frappe.db.get_value("Crop Cycle Stage", stage, "end_date")
		if stage_end and (frappe.utils.getdate() - frappe.utils.getdate(stage_end)).days <= STAGE_EDIT_GRACE_DAYS:
			return None
		return _(
			"This {0} belongs to a finished crop-cycle stage and is read-only. "
			"Ask a manager to unlock it for a correction if needed."
		).format(doctype)

	return _(
		"This {0} belongs to a crop-cycle stage that has not started yet."
	).format(doctype)


def _authorize_mobile_write(doctype, operation, name=None, values=None):
	_require_mobile_doctype(doctype, "write")
	if operation == "DELETE":
		frappe.throw(_("Mobile clients cannot delete FieldOps records."), frappe.PermissionError)
	roles = _mobile_roles()
	if (
		operation == "UPDATE"
		and not _mobile_has_management_access(roles)
		and OUTGROWER_SUPERVISOR_ROLE in roles
		and doctype in {"Outgrower", "Farm Plot"}
	):
		frappe.throw(
			_("A manager must review or update this {0} after mobile registration.").format(doctype),
			frappe.PermissionError,
		)
	if operation == "CREATE" and not _mobile_has_management_access(roles):
		allowed = set()
		for role, doctypes in MOBILE_ROLE_CREATE.items():
			if role in roles:
				allowed.update(doctypes)
		if doctype not in allowed and doctype not in MOBILE_HR_SELF_SERVICE_DOCTYPES:
			frappe.throw(
				_("Mobile users cannot create {0}; use the assigned schedule.").format(doctype),
				frappe.PermissionError,
			)
	if not _mobile_record_is_in_scope(doctype, name, values):
		frappe.throw(
			_("This {0} is outside your FieldOps assignment.").format(doctype),
			frappe.PermissionError,
		)
	_validate_mobile_visit_context(doctype, name, values)
	if operation in ("CREATE", "UPDATE") and not _mobile_has_management_access(roles):
		stage_lock_error = _mobile_stage_lock_error(doctype, name, values)
		if stage_lock_error:
			frappe.throw(stage_lock_error, frappe.PermissionError)


def _validate_mobile_visit_context(doctype, name, values):
	"""Require evidence from this officer's matching visit session."""
	if doctype not in {
		"Stage Activity", "Agronomy Report", "Inspection", "Stage Input Dispatch"
	}:
		return
	values = values or {}
	requires_visit = doctype in {"Stage Activity", "Stage Input Dispatch"} or bool(
		values.get("field_notes") or values.get("results") or values.get("takes")
		or values.get("inspection_observations")
	)
	if not requires_visit:
		return
	visit = values.get("visit") or values.get("field_visit")
	if not visit and name:
		meta = frappe.get_meta(doctype)
		field = "visit" if meta.has_field("visit") else "field_visit"
		visit = frappe.db.get_value(doctype, name, field)
	if not visit:
		frappe.throw(_("Start or resume a matching Field Visit before recording field data."), frappe.PermissionError)
	# Offline records may still carry the phone's correlation ID after the
	# visit was named by Frappe. Resolve only this officer's visit.
	if not frappe.db.exists("Field Visit", visit):
		resolved = frappe.db.get_value("Field Visit", {
			"external_id": visit, "visited_by": frappe.session.user,
		}, "name") or frappe.db.get_value("Field Visit", {
			"visit_id": visit, "visited_by": frappe.session.user,
		}, "name")
		if resolved:
			visit = resolved
			if values.get("visit"):
				values["visit"] = resolved
			if values.get("field_visit"):
				values["field_visit"] = resolved
	visit_doc = frappe.get_doc("Field Visit", visit)
	if visit_doc.visited_by != frappe.session.user:
		frappe.throw(_("The referenced Field Visit is not yours."), frappe.PermissionError)
	if visit_doc.status == "completed":
		if not _evidence_within_completed_visit(doctype, values, visit_doc):
			frappe.throw(_("Field evidence must have been captured during the completed Field Visit."), frappe.PermissionError)
	elif visit_doc.status != "in_progress":
		frappe.throw(_("The referenced Field Visit is not active."), frappe.PermissionError)
	for field in ("plot", "crop_cycle", "stage"):
		expected = values.get(field)
		actual = visit_doc.get(field)
		if expected and actual and expected != actual:
			frappe.throw(_("The Field Visit does not match this document's {0}.").format(field), frappe.PermissionError)


def _evidence_within_completed_visit(doctype, values, visit_doc):
	"""Accept offline evidence saved during a visit, then synced after closure."""
	if not visit_doc.actual_start or not visit_doc.actual_end:
		return False
	start = frappe.utils.get_datetime(visit_doc.actual_start)
	end = frappe.utils.get_datetime(visit_doc.actual_end)
	if end < start:
		return False
	if doctype == "Agronomy Report":
		captured = values.get("location_captured_at")
		if captured:
			when = frappe.utils.get_datetime(captured)
			if start <= when <= end:
				return True
		date_value = values.get("report_date")
		return bool(date_value and start.date() <= frappe.utils.getdate(date_value) <= end.date())
	if doctype == "Stage Activity":
		date_value = values.get("activity_date")
		return bool(date_value and start.date() <= frappe.utils.getdate(date_value) <= end.date())
	if doctype == "Inspection":
		captured = [row.get("captured_at") for row in values.get("takes") or []]
		captured = [value for value in captured if value]
		if not captured:
			captured = [values.get("started_at") or values.get("completed_at")]
		return bool(captured and all(value and start <= frappe.utils.get_datetime(value) <= end for value in captured))
	if doctype == "Stage Input Dispatch":
		# Dispatch Date is deliberately a Date field. Mobile deliveries may be
		# recorded offline during the visit and uploaded only after the officer
		# completes it, so compare the recorded delivery day with the visit
		# window instead of requiring the visit to remain open during sync.
		date_value = values.get("dispatch_date")
		return bool(
			date_value
			and start.date() <= frappe.utils.getdate(date_value) <= end.date()
		)
	return False


@frappe.whitelist()
def mobile_unlock_stage_document(doctype, name, reason=None):
	"""Let a manager reopen one Stage Activity/Agronomy Report for a
	correction. Only finished (past) stage records qualify — a current-stage
	record isn't locked and needs no override, and an upcoming-stage record
	has nothing to correct yet. Recorded on the doc itself so the override is
	visible and auditable wherever the record is later read."""
	_require_mobile_doctype(doctype, "write")
	if doctype not in STAGE_LOCKED_DOCTYPES:
		frappe.throw(_("{0} does not support stage-lock overrides.").format(doctype), frappe.PermissionError)
	if not _mobile_has_management_access(_mobile_roles()):
		frappe.throw(
			_("Only a manager can unlock a finished stage's record."),
			frappe.PermissionError,
		)
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} was not found.").format(doctype, name), frappe.DoesNotExistError)

	stage_order, current_order, _stage = _mobile_stage_order(doctype, name, None)
	if stage_order is None or current_order is None:
		frappe.throw(
			_("This {0}'s stage could not be resolved; cannot verify it is finished.").format(doctype),
			frappe.ValidationError,
		)
	if stage_order >= current_order:
		frappe.throw(
			_("Only a finished (past) stage's {0} can be unlocked for correction.").format(doctype),
			frappe.PermissionError,
		)

	frappe.db.set_value(
		doctype,
		name,
		{
			"stage_lock_override_by": frappe.session.user,
			"stage_lock_override_at": frappe.utils.now_datetime(),
			"stage_lock_override_reason": (reason or "").strip() or None,
		},
	)
	frappe.db.commit()
	return {"success": True, "name": name}


def _strip_server_owned_mobile_fields(doctype, values):
	values = dict(values or {})
	for fieldname in MOBILE_SERVER_OWNED_FIELDS.get(doctype, set()):
		values.pop(fieldname, None)
	if doctype == "Outgrower" and OUTGROWER_SUPERVISOR_ROLE in _mobile_roles():
		# The assignment is derived from the authenticated session, never from
		# editable mobile input. Managers retain review/confirmation authority.
		values["assigned_supervisor"] = frappe.session.user
	if doctype == "Field Trip":
		values["field_officer"] = frappe.session.user
		values["employee"] = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		for fieldname in ("manager_review_status", "reviewed_by", "reviewed_at", "review_notes", "calculated_distance_km"):
			values.pop(fieldname, None)
	if doctype == "Field Visit":
		values["visited_by"] = frappe.session.user
		values["external_id"] = values.get("external_id") or values.get("visit_id")
		values.pop("distance_from_plot", None)
	if doctype == "Inspection":
		# Enables create-scope validation while preventing inspectors from
		# assigning inspections to another user through a crafted payload.
		values["assigned_to"] = frappe.session.user
		for take in values.get("takes") or []:
			take["captured_by"] = frappe.session.user
			if take.get("positioning_override"):
				take["positioning_override_by"] = frappe.session.user
		for observation in values.get("inspection_observations") or []:
			observation["captured_by"] = frappe.session.user
			observation["captured_at"] = frappe.utils.now_datetime()
		if values.get("inspection_template"):
			existing_version = None
			existing_snapshot = None
			if values.get("name") and frappe.db.exists("Inspection", values.get("name")):
				existing_version, existing_snapshot = frappe.db.get_value(
					"Inspection",
					values.get("name"),
					["template_version", "configuration_snapshot"],
				)
			version = frappe.db.get_value(
				"Inspection Template",
				values.get("inspection_template"),
				"configuration_version",
			)
			values["template_version"] = existing_version or version or 1
			values["configuration_snapshot"] = (
				existing_snapshot
				or _inspection_configuration_snapshot(values.get("inspection_template"))
			)
		_validate_mobile_take_evidence(values)
	if doctype == "Agronomy Report" and "results" in values:
		raw_fields = {
			"parameter_code", "value_captured", "numeric_value", "text_value", "date_value", "remarks"
		}
		raw_results = []
		for row in values.get("results") or []:
			filtered = {key: value for key, value in row.items() if key in raw_fields}
			if "value_captured" not in filtered:
				filtered["value_captured"] = int(
					any(
						fieldname in row and row.get(fieldname) not in (None, "")
						for fieldname in ("numeric_value", "text_value", "date_value")
					)
				)
			raw_results.append(filtered)
		values["results"] = raw_results
	if doctype == "Seed Harvest Quality Assessment":
		values["inspected_by"] = frappe.session.user
	if doctype in MOBILE_HR_SELF_SERVICE_DOCTYPES:
		employees = _get_attendance_employee_ids({})
		if not employees:
			frappe.throw(
				_("Your Frappe user is not linked to an active Employee record."),
				frappe.PermissionError,
			)
		employee = employees[0]
		values["employee"] = employee
		company = frappe.db.get_value("Employee", employee, "company")
		if company:
			values["company"] = company
		if doctype == "Leave Application":
			values.setdefault("posting_date", frappe.utils.today())
		if doctype == "Employee Advance":
			currency = frappe.db.get_value("Company", company, "default_currency") if company else None
			values["currency"] = values.get("currency") or currency
			values["exchange_rate"] = values.get("exchange_rate") or 1
		if doctype == "Expense Claim" and not values.get("expenses"):
			amount = values.pop("total_claimed_amount", None)
			expense_type = values.pop("category", None)
			if amount is not None and expense_type:
				values["expenses"] = [{
					"expense_date": values.get("posting_date") or frappe.utils.today(),
					"expense_type": expense_type,
					"description": values.pop("description", None),
					"amount": amount,
					"sanctioned_amount": amount,
				}]
	return values


def _inspection_configuration_snapshot(template):
	"""Freeze the rules used for an inspection so later manager edits are auditable."""
	if not template:
		return None
	from naseco_fieldopsbackend.inspection_scheduler import inspection_configuration_snapshot
	return inspection_configuration_snapshot(template)


def _validate_mobile_take_evidence(values):
	evidence = values.get("take_evidence") or []
	take_numbers = {cint(row.get("take_number")) for row in values.get("takes") or []}
	template = values.get("inspection_template")
	if template:
		from naseco_fieldopsbackend.inspection_scheduler import get_template_standard_rows
		configured_parameters = {row.parameter for row in get_template_standard_rows(template) if row.parameter}
	else:
		configured_parameters = set()
	seen_ids = set()
	for row in evidence:
		take_number = cint(row.get("take_number"))
		if take_number not in take_numbers:
			frappe.throw(_("Evidence references take {0}, which does not exist.").format(take_number))
		if row.get("parameter") and row.get("parameter") not in configured_parameters:
			frappe.throw(_("Evidence parameter {0} is not configured for this inspection.").format(row.get("parameter")))
		if not row.get("file"):
			frappe.throw(_("Every take evidence row requires an uploaded file."))
		if not row.get("external_id") or row.get("external_id") in seen_ids:
			frappe.throw(_("Every take evidence file requires a unique mobile evidence ID."))
		seen_ids.add(row.get("external_id"))
		row["captured_by"] = frappe.session.user
		row["captured_at"] = row.get("captured_at") or frappe.utils.now_datetime()

	if not configured_parameters:
		return
	policies = {
		row.name: row
		for row in frappe.get_all(
			"Inspection Parameter",
			filters={"name": ["in", list(configured_parameters)]},
			fields=["name", "evidence_policy", "minimum_evidence_files", "maximum_evidence_files", "allow_multiple_files"],
		)
	}
	evidence_counts = defaultdict(int)
	for row in evidence:
		if row.get("parameter"):
			evidence_counts[(cint(row.get("take_number")), row.get("parameter"))] += 1
	for (take_number, parameter), count in evidence_counts.items():
		policy = policies.get(parameter)
		if not policy:
			continue
		maximum = cint(policy.maximum_evidence_files) or 10
		if not cint(policy.allow_multiple_files):
			maximum = 1
		if count > maximum:
			frappe.throw(
				_("Take {0} has {1} evidence files for {2}; the configured maximum is {3}.").format(
					take_number, count, parameter, maximum
				)
			)
	for result in values.get("take_results") or []:
		parameter = result.get("parameter")
		policy = policies.get(parameter)
		if not policy:
			continue
		required = cint(policy.minimum_evidence_files)
		if policy.evidence_policy == "Required":
			required = max(required, 1)
		elif policy.evidence_policy == "Required on Non-zero" and cint(result.get("observed_count")) > 0:
			required = max(required, 1)
		else:
			continue
		key = (cint(result.get("take_number")), parameter)
		if evidence_counts[key] < required:
			frappe.throw(
				_("Take {0} requires at least {1} evidence file(s) for {2}.").format(
					key[0], required, parameter
				)
			)


def _normalize_uom_doc_data(data):
	data = dict(data or {})
	uom_name = normalize_uom(data.get("uom_name") or data.get("unitName") or data.get("name"))
	data["doctype"] = "UOM"
	data["uom_name"] = uom_name
	if data.get("name"):
		data["name"] = uom_name
	data.pop("unit_name", None)
	data.pop("unitName", None)
	return data


_meta_cache = {}


def _get_meta(doctype):
	if doctype not in _meta_cache:
		_meta_cache[doctype] = frappe.get_meta(doctype)
	return _meta_cache[doctype]



def _mobile_datetime(value):
	"""Convert an instant to Frappe's naive site-local SQL datetime."""
	from zoneinfo import ZoneInfo
	parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
	if parsed.tzinfo is not None:
		parsed = parsed.astimezone(ZoneInfo(frappe.utils.get_system_timezone())).replace(tzinfo=None)
	return parsed


def _normalize_mobile_temporal_fields(doctype, data):
	"""Normalize by DocType metadata, including child tables, never by key guesses."""
	from datetime import date, time
	result = dict(data)
	# Frappe owns audit timestamps; client updatedAt is only a conflict token.
	for key in ("creation", "modified", "createdAt", "updatedAt", "modified_by", "owner"):
		result.pop(key, None)
	for field in _get_meta(doctype).fields:
		key = field.fieldname
		if key not in result:
			continue
		value = result[key]
		if field.fieldtype in ("Table", "Table MultiSelect"):
			result[key] = [_normalize_mobile_temporal_fields(field.options, row) for row in value or []]
		elif field.fieldtype in ("Date", "Datetime", "Time"):
			if value is None or value == "":
				result[key] = None
				continue
			try:
				if field.fieldtype == "Datetime":
					result[key] = _mobile_datetime(value).isoformat(sep=" ", timespec="microseconds")
				elif field.fieldtype == "Date":
					# Calendar dates must not shift when a device supplies an offset.
					result[key] = date.fromisoformat(str(value).strip()[:10]).isoformat()
				elif isinstance(value, str):
					parsed = time.fromisoformat(value.strip())
					if parsed.tzinfo is not None:
						raise ValueError("Time fields require a local time without an offset")
					result[key] = parsed.isoformat(timespec="microseconds")
			except (ValueError, TypeError, OverflowError) as exc:
				raise ValueError(f"Invalid {field.fieldtype} for {doctype}.{key}: {exc}") from exc
	return result

def _filter_fields(doctype, data):
	meta = _get_meta(doctype)
	valid_fields = {df.fieldname for df in meta.fields}
	valid_fields.update({"doctype", "name"})
	return _normalize_mobile_temporal_fields(doctype, {k: v for k, v in data.items() if k in valid_fields})


def _resolve_employee_fields(doctype, payload, result):
	meta = _get_meta(doctype)
	if doctype in MOBILE_HR_SELF_SERVICE_DOCTYPES:
		employees = _get_attendance_employee_ids({})
		if employees and meta.has_field("employee"):
			result["employee"] = employees[0]
		return _complete_mobile_hr_fields(doctype, payload, result)
	user_id = (payload or {}).get("userId") or (payload or {}).get("userEmail") or (payload or {}).get("email")
	if user_id and meta.has_field("employee"):
		emp = frappe.db.get_value("Employee", {"user_id": user_id}, "name")
		if not emp and (payload or {}).get("userEmail"):
			emp = frappe.db.get_value("Employee", {"user_id": (payload or {}).get("userEmail")}, "name")
		if emp:
			result["employee"] = emp

	if doctype == "Attendance":
		if (payload or {}).get("date"):
			result.setdefault("attendance_date", (payload or {}).get("date"))
	if doctype == "Employee Checkin":
		if (payload or {}).get("time"):
			result.setdefault("time", (payload or {}).get("time"))
		if (payload or {}).get("logType"):
			result.setdefault("log_type", (payload or {}).get("logType"))
	if doctype == "Leave Application":
		if (payload or {}).get("leaveType"):
			result.setdefault("leave_type", (payload or {}).get("leaveType"))
		if (payload or {}).get("fromDate"):
			result.setdefault("from_date", (payload or {}).get("fromDate"))
		if (payload or {}).get("toDate"):
			result.setdefault("to_date", (payload or {}).get("toDate"))
		if (payload or {}).get("isHalfDay") is not None:
			result.setdefault("half_day", (payload or {}).get("isHalfDay"))
		if (payload or {}).get("reason"):
			result.setdefault("description", (payload or {}).get("reason"))
	if doctype == "Employee Advance":
		if (payload or {}).get("postingDate"):
			result.setdefault("posting_date", (payload or {}).get("postingDate"))
		if (payload or {}).get("purpose"):
			result.setdefault("purpose", (payload or {}).get("purpose"))
		if (payload or {}).get("amount") is not None:
			if meta.has_field("advance_amount"):
				result.setdefault("advance_amount", (payload or {}).get("amount"))
			elif meta.has_field("amount"):
				result.setdefault("amount", (payload or {}).get("amount"))
	if doctype == "Expense Claim":
		if (payload or {}).get("dateSubmitted"):
			result.setdefault("posting_date", (payload or {}).get("dateSubmitted"))
		if (payload or {}).get("amount") is not None:
			if meta.has_field("total_claimed_amount"):
				result.setdefault("total_claimed_amount", (payload or {}).get("amount"))
			elif meta.has_field("amount"):
				result.setdefault("amount", (payload or {}).get("amount"))

	return result


def _complete_mobile_hr_fields(doctype, payload, result):
	"""Supply required HRMS fields from the authenticated employee context."""
	employee = result.get("employee")
	company = frappe.db.get_value("Employee", employee, "company") if employee else None
	if company:
		result["company"] = company
	if doctype == "Leave Application":
		result.setdefault("posting_date", frappe.utils.today())
	elif doctype == "Employee Advance":
		currency = frappe.db.get_value("Company", company, "default_currency") if company else None
		result["currency"] = result.get("currency") or currency
		result["exchange_rate"] = result.get("exchange_rate") or 1
	elif doctype == "Expense Claim" and not result.get("expenses"):
		result["posting_date"] = (
			(payload or {}).get("dateSubmitted")
			or result.get("posting_date")
			or frappe.utils.today()
		)
		amount = (payload or {}).get("amount")
		expense_type = (payload or {}).get("category")
		if amount is not None and expense_type:
			result["expenses"] = [{
				"expense_date": result.get("posting_date") or frappe.utils.today(),
				"expense_type": expense_type,
				"description": (payload or {}).get("description"),
				"amount": amount,
				"sanctioned_amount": amount,
			}]
	return result


def _normalize_outgrower_payload(payload):
	data = dict(payload or {})
	if "bank_account" not in data and "bankAccount" in data:
		data["bank_account"] = data.get("bankAccount")
	if "outgrower_type" not in data and "outgrowerType" in data:
		data["outgrower_type"] = data.get("outgrowerType")
	return data


def _enrich_outgrower_aliases(record):
	if not isinstance(record, dict):
		return record
	if "bank_account" in record and "bankAccount" not in record:
		record["bankAccount"] = record.get("bank_account")
	if "bankAccount" in record and "bank_account" not in record:
		record["bank_account"] = record.get("bankAccount")
	if "outgrower_type" in record and "outgrowerType" not in record:
		record["outgrowerType"] = record.get("outgrower_type")
	if "outgrowerType" in record and "outgrower_type" not in record:
		record["outgrower_type"] = record.get("outgrowerType")
	return record


def _get_request_args(kwargs=None):
	args = {}
	try:
		form_dict = dict(getattr(frappe.local, "form_dict", {}) or {})
		args.update(form_dict)
	except Exception:
		pass
	try:
		if getattr(frappe, "request", None):
			args.update(dict(frappe.request.args or {}))
			args.update(dict(frappe.request.form or {}))
	except Exception:
		pass
	args.update(kwargs or {})
	return args


def _as_list(value):
	if value is None:
		return []
	if isinstance(value, (list, tuple, set)):
		return [str(v).strip() for v in value if str(v).strip()]
	if isinstance(value, str):
		v = value.strip()
		if not v:
			return []
		if v.startswith("[") and v.endswith("]"):
			try:
				parsed = json.loads(v)
				if isinstance(parsed, list):
					return [str(x).strip() for x in parsed if str(x).strip()]
			except Exception:
				pass
		if "," in v:
			return [x.strip() for x in v.split(",") if x.strip()]
		return [v]
	return [str(value).strip()]


def _parse_iso_datetime(value):
	if not value:
		return None
	if isinstance(value, datetime):
		return value
	if isinstance(value, str):
		try:
			return datetime.fromisoformat(value.replace("Z", "+00:00"))
		except Exception:
			return None
	return None


def _get_identity_emails(args):
	emails = set()
	for key in (
		"attendance_user_email",
		"attendance_user",
		"attendance_user_id",
		"user_email",
		"user_id",
		"assigned_to",
	):
		emails.update(_as_list(args.get(key)))
	return sorted(emails)


def _get_attendance_employee_ids(args):
	# Never trust client identity hints for HR data access.
	user = frappe.session.user
	if not user or user == "Guest":
		return []
	return frappe.get_all("Employee", filters={"user_id": user}, pluck="name")


def _build_attendance_filters(args, modified_since=None):
	employee_ids = _get_attendance_employee_ids(args)
	if not employee_ids:
		return None

	start_dt = _parse_iso_datetime(args.get("attendance_month_start"))
	end_dt = _parse_iso_datetime(args.get("attendance_month_end"))
	if not start_dt or not end_dt:
		return None

	filters = [
		["employee", "in", employee_ids],
		["attendance_date", ">=", start_dt.date().isoformat()],
		["attendance_date", "<", end_dt.date().isoformat()],
	]
	if modified_since:
		filters.append(["modified", ">", modified_since])
	return filters


def _build_employee_checkin_filters(args, modified_since=None):
	meta = _get_meta("Employee Checkin")
	filters = []

	employee_ids = _get_attendance_employee_ids(args)
	if employee_ids and meta.has_field("employee"):
		filters.append(["employee", "in", employee_ids])
	else:
		emails = [frappe.session.user] if frappe.session.user != "Guest" else []
		# Fallback for deployments with custom user fields on Employee Checkin
		if emails and meta.has_field("user_id"):
			filters.append(["user_id", "in", emails])
		elif emails and meta.has_field("user_email"):
			filters.append(["user_email", "in", emails])

	if not filters:
		return None

	# If month window is sent, constrain checkins by checkin time too.
	start_dt = _parse_iso_datetime(args.get("attendance_month_start"))
	end_dt = _parse_iso_datetime(args.get("attendance_month_end"))
	if start_dt and end_dt and meta.has_field("time"):
		filters.append(["time", ">=", start_dt.strftime("%Y-%m-%d %H:%M:%S")])
		filters.append(["time", "<", end_dt.strftime("%Y-%m-%d %H:%M:%S")])

	if modified_since:
		filters.append(["modified", ">", modified_since])

	return filters


@frappe.whitelist()
def bulk_sync(data):
	"""
	Bulk create/update records from mobile app.

	Accepted formats:
	- [{"doctype": "DocType", "operation": "CREATE/UPDATE/DELETE", "doc": {...}}]
	- {"data": [{"storeName": "outgrowers", "recordId": "...", "payload": {...}, "operation": "SYNC"}]}
	"""
	try:
		records = json.loads(data) if isinstance(data, str) else data
		if isinstance(records, dict) and "data" in records:
			records = records.get("data")

		results = []
		for record in records or []:
			try:
				if record.get("storeName") or record.get("store_name") or record.get("payload"):
					# Delegate to push_sync_data-style payloads
					out = push_sync_data({"data": [record]})
					results.extend(out.get("results", []))
					continue

				doctype = _resolve_doctype(record.get("doctype"), strict=True)
				operation = (record.get("operation") or "").upper()
				doc_data = record.get("doc") or {}
				if doctype == "Outgrower":
					doc_data = _normalize_outgrower_payload(doc_data)
				if doctype == "UOM":
					doc_data = _normalize_uom_doc_data(doc_data)
				doc_data = _strip_server_owned_mobile_fields(doctype, doc_data)
				doc_data = _normalize_mobile_temporal_fields(doctype, doc_data)
				doc_name = doc_data.get("name")
				_authorize_mobile_write(doctype, operation, doc_name, doc_data)

				result = {"doctype": doctype, "operation": operation, "status": "success"}

				if operation == "CREATE":
					doc_data["doctype"] = doctype
					doc = frappe.get_doc(doc_data)
					doc.insert(ignore_permissions=True)
					result["name"] = doc.name
				elif operation == "UPDATE":
					if doc_name and frappe.db.exists(doctype, doc_name):
						doc = frappe.get_doc(doctype, doc_name)
						doc.update(doc_data)
						doc.save(ignore_permissions=True)
						result["name"] = doc.name
					else:
						doc = frappe.get_doc(doc_data)
						doc.insert(ignore_permissions=True)
						result["name"] = doc.name
				elif operation == "DELETE":
					if doc_name and frappe.db.exists(doctype, doc_name):
						frappe.delete_doc(doctype, doc_name, ignore_permissions=True)
						result["name"] = doc_name
					else:
						result["status"] = "not_found"
						result["message"] = f"Document {doctype} {doc_name} not found"
				else:
					result["status"] = "error"
					result["message"] = f"Unknown operation: {operation}"

				log_sync(frappe.session.user, doctype, doc_data.get("name"), operation, result["status"])
				results.append(result)
			except Exception as e:
				results.append({"status": "error", "doctype": record.get("doctype"), "error": str(e)})

		frappe.db.commit()
		return {"success": True, "results": results}
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(f"Bulk sync error: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_modified_records(last_sync_timestamp=None, doctypes=None, doctype=None, since=None, **kwargs):
	"""
	Get all records modified since last sync timestamp

	Args:
		last_sync_timestamp: ISO format timestamp of last sync
		since: Alternative query param used by some clients
		doctypes: Optional JSON list of doctypes to fetch. If None, fetches all synced doctypes.
		doctype: Optional single doctype name

	Returns:
		JSON response with modified records grouped by doctype
	"""
	try:
		args = _get_request_args(kwargs)
		if since and not last_sync_timestamp:
			last_sync_timestamp = since
		# Parse last sync timestamp
		if isinstance(last_sync_timestamp, str):
			last_sync = datetime.fromisoformat(last_sync_timestamp.replace('Z', '+00:00'))
		else:
			last_sync = last_sync_timestamp

		# Default synced doctypes
		default_doctypes = [
			"Outgrower", "Farm Plot", "Crop Cycle", "Crop Cycle Stage",
			"Field Visit", "Inspection", "Agronomy Report", "Field Corrective Action",
			"Plot Crop Assignment", "Stage Activity",
			"Stage Input Request", "Stage Input Dispatch",
			"Attendance", "Leave Application", "Employee Advance", "Expense Claim"
		]

		# Parse doctypes filter
		if doctype:
			target_doctypes = [doctype]
		elif doctypes:
			target_doctypes = json.loads(doctypes) if isinstance(doctypes, str) else doctypes
		else:
			target_doctypes = default_doctypes
		target_doctypes = [
			item
			for item in target_doctypes
			if _resolve_doctype(item, strict=True) in _mobile_allowed_doctypes("read")
		]

		modified_records = {}

		for requested_doctype in target_doctypes:
			try:
				doctype = _resolve_doctype(requested_doctype, strict=True)
				_require_mobile_doctype(doctype, "read")
				filters = []
				if doctype == "Attendance":
					filters = _build_attendance_filters(args, last_sync)
					if not filters:
						modified_records[doctype] = []
						continue
				elif doctype == "Employee Checkin":
					filters = _build_employee_checkin_filters(args, last_sync)
					if not filters:
						modified_records[doctype] = []
						continue
				elif last_sync:
					filters = [["modified", ">", last_sync]]
				scope_names = _mobile_scope_names(doctype)
				if scope_names is not None:
					if not scope_names:
						modified_records[doctype] = []
						continue
					filters.append(["name", "in", list(scope_names)])

				# Get modified records
				records = frappe.get_all(
					doctype,
					filters=filters,
					fields=["*"],
					order_by="modified asc"
				)

				# Get full documents with child tables
				full_records = []
				for record in records:
					try:
						doc = frappe.get_doc(doctype, record.name)
						doc_dict = doc.as_dict()
						if doctype == "Outgrower":
							doc_dict = _enrich_outgrower_aliases(doc_dict)
						full_records.append(
							_attach_user_full_names(doctype, doc_dict, doc_dict)
						)
					except Exception as e:
						frappe.log_error(f"Error fetching {doctype} {record.name}: {str(e)}")

				if full_records or doctype == "Attendance":
					modified_records[doctype] = full_records

			except Exception as e:
				frappe.log_error(f"Error fetching modified {doctype}: {str(e)}")

		return {
			"success": True,
			"modified_records": modified_records,
			"data": modified_records,
			"sync_timestamp": datetime.now().isoformat()
		}

	except Exception as e:
		frappe.log_error(f"Get modified records error: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def get_reference_data():
	"""
	Get all reference/metadata entities for mobile app

	Returns:
		JSON response with all reference data
	"""
	try:
		reference_data = {}

		# List of reference doctypes
		reference_doctypes = {
			"Crop": ["*"],
			"Crop Variety": ["*"],
			"Season": ["*"],
			"Crop Recipe": ["*"],
			"Visit Type": ["*"],
			"Region": ["*"],
			"UOM": ["*"],
			"Inspection Attribute": ["*"],
			"Inspection Parameter": ["*"],
			"Inspection Template": ["*"],
			"Inspection Standard": ["*"],
			"Inspection Template Parameter": ["*"],
			"Inspection Template Applicability": ["*"],
			"Agronomy Activity Template": ["*"],
			"Agronomy Report Template": ["*"],
			"Crop Cycle Stage": ["*"]
		}

		for doctype, fields in reference_doctypes.items():
			try:
				_require_mobile_doctype(doctype, "read")
				records = frappe.get_all(doctype, fields=fields)
				response_key = "Unit" if doctype == "UOM" else doctype
				if doctype == "UOM":
					records = [
						{
							**record,
							"unit_name": record.get("uom_name"),
							"unitName": record.get("uom_name"),
						}
						for record in records
					]
				reference_data[response_key] = records
			except Exception as e:
				frappe.log_error(f"Error fetching reference {doctype}: {str(e)}")

		positioning_settings = _get_mobile_positioning_settings()
		reference_data["FieldOps Settings"] = positioning_settings
		reference_data["positioningSettings"] = positioning_settings

		return {
			"success": True,
			"reference_data": reference_data,
			"data": reference_data,
			"timestamp": datetime.now().isoformat()
		}

	except Exception as e:
		frappe.log_error(f"Get reference data error: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}




@frappe.whitelist()
def get_inspection_positioning_settings():
	"""Return the server-owned QA positioning standard for mobile clients."""
	return {
		"success": True,
		"data": _get_mobile_positioning_settings(),
	}


def _get_mobile_positioning_settings():
	from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection import (
		get_positioning_settings,
		can_override_positioning,
	)

	settings = get_positioning_settings()
	return {
		"targetTakeSpacingM": settings.target_take_spacing_m,
		"minimumTakeSpacingM": settings.minimum_take_spacing_m,
		"maximumTakeSpacingM": settings.maximum_take_spacing_m,
		"minimumSpacingCompliancePercent": settings.minimum_spacing_compliance_percent,
		"preferredGpsAccuracyM": settings.preferred_gps_accuracy_m,
		"maximumGpsAccuracyM": settings.maximum_gps_accuracy_m,
		"minimumLocationSamples": settings.minimum_location_samples,
		"locationCaptureTimeoutSeconds": settings.location_capture_timeout_seconds,
		"maximumLocationAgeSeconds": settings.maximum_location_age_seconds,
		"allowPositioningOverride": settings.allow_positioning_override,
		"canOverride": bool(can_override_positioning(settings)),
		"overrideUser": frappe.session.user,
	}


@frappe.whitelist()
def get_sync_data(last_sync=None, officer_region=None, **kwargs):
	"""
	Get all synced data since last_sync. Returns data grouped by store name.
	"""
	try:
		_sync_verified_inter_row_spacing()
		args = _get_request_args(kwargs)
		if last_sync:
			last_sync_dt = datetime.fromisoformat(str(last_sync).replace('Z', '+00:00'))
		else:
			last_sync_dt = None

		# Main synced doctypes are filtered again by role and assignment below.
		sync_doctypes = [
			"Attendance",
			"Employee Checkin",
			"Outgrower",
			"Farm Plot",
			"Crop Cycle",
			"Crop Cycle Stage",
			"Field Visit",
			"Field Trip",
			"Inspection",
			"Agronomy Report",
			"Field Corrective Action",
			"Plot Crop Assignment",
			"Stage Activity",
			"Stage Input Request",
			"Stage Input Dispatch",
			"Crop Production Lot",
			"Seed Harvest Quality Assessment",
			"Expense Claim",
			"Leave Application",
			"Employee Advance",
		]
		sync_doctypes = [
			doctype
			for doctype in sync_doctypes
			if doctype in _mobile_allowed_doctypes("read")
		]

		# Reference doctypes (always include)
		reference_doctypes = [
			"Crop",
			"Crop Variety",
			"Season",
			"Crop Recipe",
			"Visit Type",
			"Region",
			"UOM",
			"Inspection Attribute",
			"Inspection Parameter",
			"Inspection Template",
			"Inspection Standard",
			"Inspection Template Parameter",
			"Inspection Template Applicability",
			"Agronomy Activity Template",
			"Agronomy Report Template",
			"Crop Cycle Stage",
		]

		data = {}
		# These parent records define the context of assigned inspections. Return
		# their complete scoped set on every sync so a newly assigned inspection
		# cannot reference an older Outgrower/Farm Plot/Crop Cycle that the device
		# has never downloaded.
		assignment_context_doctypes = {"Outgrower", "Farm Plot", "Crop Cycle"}

		# Optional region filter for outgrowers and related plots
		region_outgrowers = None
		if officer_region:
			region_outgrowers = [
				row.name for row in frappe.get_all("Outgrower", filters={"region": officer_region}, fields=["name"])
			]

		for doctype in sync_doctypes:
			filters = []

			if doctype == "Attendance":
				filters = _build_attendance_filters(args, last_sync_dt)
				store = DOCTYPE_TO_STORE.get(doctype, doctype)
				if not filters:
					data[store] = []
					continue
			elif doctype == "Employee Checkin":
				filters = _build_employee_checkin_filters(args, last_sync_dt)
				store = DOCTYPE_TO_STORE.get(doctype, doctype)
				if not filters:
					data[store] = []
					continue
			elif last_sync_dt and doctype not in assignment_context_doctypes:
				filters.append(["modified", ">", last_sync_dt])
			scope_names = _mobile_scope_names(doctype)
			if scope_names is not None:
				if not scope_names:
					data[DOCTYPE_TO_STORE.get(doctype, doctype)] = []
					continue
				filters.append(["name", "in", list(scope_names)])

			if officer_region and doctype == "Outgrower":
				filters.append(["region", "=", officer_region])
			if officer_region and doctype == "Farm Plot" and region_outgrowers:
				filters.append(["outgrower", "in", region_outgrowers])

			full_docs = []
			if doctype in SYNC_DOCTYPES_WITHOUT_CHILD_TABLES:
				# One query for every row instead of one frappe.get_doc() per
				# row — safe because this doctype has no child tables for
				# _map_doc_to_mobile to lose.
				rows = frappe.get_all(doctype, filters=filters, fields=["*"], order_by="modified asc")
				for row in rows:
					try:
						full_docs.append(_map_doc_to_mobile(doctype, row))
					except Exception:
						frappe.log_error(f"Error mapping {doctype} {row.get('name')}")
			else:
				records = frappe.get_all(doctype, filters=filters, fields=["name"], order_by="modified asc")
				for row in records:
					try:
						doc = frappe.get_doc(doctype, row.name).as_dict()
						full_docs.append(_map_doc_to_mobile(doctype, doc))
					except Exception:
						frappe.log_error(f"Error fetching {doctype} {row.name}")

			store = DOCTYPE_TO_STORE.get(doctype, doctype)
			data[store] = full_docs

		# Always include reference data
		for doctype in reference_doctypes:
			try:
				_require_mobile_doctype(doctype, "read")
				records = frappe.get_all(doctype, fields=["name"], order_by="modified asc")
				full_docs = [
					_map_doc_to_mobile(doctype, frappe.get_doc(doctype, row.name).as_dict())
					for row in records
				]
				store = DOCTYPE_TO_STORE.get(doctype, doctype)
				data[store] = full_docs
			except Exception as e:
				frappe.log_error(f"Error fetching reference {doctype}: {str(e)}")

		_merge_confirmed_cycle_context(data)

		deletions = _get_sync_deletions(sync_doctypes, last_sync_dt)

		return {
			"data": data,
			"deletions": deletions,
			"server_time": datetime.now().isoformat(),
			"last_sync": last_sync,
		}
	except Exception as e:
		frappe.log_error(f"Get sync data error: {str(e)}")
		return {"error": str(e)}


def _get_sync_deletions(sync_doctypes, last_sync_dt):
	"""
	Records deleted from Frappe (e.g. a manager deleting an Outgrower from
	the desk) simply vanish from the get_all() results above — indistinguishable,
	to an offline client holding a stale local copy, from "never existed" or
	"out of scope". Frappe already tombstones every frappe.delete_doc() call
	into the built-in "Deleted Document" table, so surface that as an explicit
	feed instead of leaving mobile with no signal to remove its local copy.

	Not scoped by user/region: a deletion for a record mobile never held
	locally is a harmless no-op there, and the deleted record's own scoping
	fields are no longer queryable once it's gone.
	"""
	if not sync_doctypes:
		return {}
	filters = [["deleted_doctype", "in", sync_doctypes]]
	if last_sync_dt:
		filters.append(["creation", ">", last_sync_dt])
	rows = frappe.get_all(
		"Deleted Document",
		filters=filters,
		fields=["deleted_doctype", "deleted_name"],
		order_by="creation asc",
		ignore_permissions=True,
	)
	deletions = {}
	for row in rows:
		store = DOCTYPE_TO_STORE.get(row.deleted_doctype, row.deleted_doctype)
		deletions.setdefault(store, []).append(row.deleted_name)
	return deletions


def _merge_confirmed_cycle_context(data):
	"""Always include authorized confirmed cycles, their parents and schedules."""
	allowed = _mobile_allowed_doctypes("read")
	if "Crop Cycle" not in allowed:
		return
	names = _mobile_scope_names("Crop Cycle")
	filters = {"planting_date_confirmed": 1}
	if names is not None:
		if not names:
			return
		filters["name"] = ["in", list(names)]
	cycles = frappe.get_all("Crop Cycle", filters=filters, fields=["name", "plot"])
	if not cycles:
		return
	cycle_names = [row.name for row in cycles]
	plots = {row.plot for row in cycles if row.plot}
	growers = frappe.get_all("Farm Plot", filters={"name": ["in", list(plots)]}, pluck="outgrower") if plots else []
	context = {"Crop Cycle": cycle_names, "Farm Plot": list(plots), "Outgrower": list(set(growers))}
	context["Crop Cycle Stage"] = frappe.get_all("Crop Cycle Stage", filters={"crop_cycle": ["in", cycle_names]}, pluck="name")
	for doctype in ("Stage Activity", "Agronomy Report", "Inspection"):
		if doctype not in allowed:
			continue
		task_names = _mobile_scope_names(doctype)
		task_filters = {"crop_cycle": ["in", cycle_names]}
		if task_names is not None:
			if not task_names:
				continue
			task_filters["name"] = ["in", list(task_names)]
		context[doctype] = frappe.get_all(doctype, filters=task_filters, pluck="name")
	for doctype, doc_names in context.items():
		if doctype not in allowed:
			continue
		store = DOCTYPE_TO_STORE.get(doctype, doctype)
		merged = {row.get("name"): row for row in data.get(store, [])}
		for name in doc_names:
			if name:
				merged[name] = _map_doc_to_mobile(doctype, frappe.get_doc(doctype, name).as_dict())
		data[store] = list(merged.values())


@frappe.whitelist()
def push_sync_data(data):
	"""
	Create/update records pushed from mobile app.
	"""
	try:
		visit_lock = None
		records = json.loads(data) if isinstance(data, str) else data
		if isinstance(records, dict) and "data" in records:
			records = records.get("data")

		# Serialize starts for this officer, including independent mobile devices.
		# Keep the lock until the batch commits so another request cannot pass
		# FieldVisit.validate() before this visit becomes visible.
		if any((row.get("storeName") or row.get("store_name") or row.get("doctype"))
			in ("visits", "Visit", "Field Visit") for row in records or []):
			import hashlib
			visit_lock = hashlib.sha256(
				("active-field-visit:" + frappe.session.user).encode()
			).hexdigest()
			if not frappe.db.sql("SELECT GET_LOCK(%s, 15)", (visit_lock,))[0][0]:
				frappe.throw("Another Field Visit start is in progress. Retry sync shortly.")

		results = []
		for record in records or []:
			try:
				store = record.get("storeName") or record.get("store_name") or record.get("doctype")
				doctype = _resolve_doctype(store, strict=True)
				payload = record.get("payload") or record.get("doc") or {}
				if doctype == "Outgrower":
					payload = _normalize_outgrower_payload(payload)
				operation = (record.get("operation") or "SYNC").upper()
				record_id = record.get("recordId") or payload.get("id") or payload.get("name")
				force = record.get("force") or payload.get("force")
				if doctype == "UOM":
					record_id = normalize_uom(record_id or payload.get("unitName") or payload.get("uom_name"))

				mapped = _map_mobile_to_doc(doctype, payload)
				mapped = _strip_server_owned_mobile_fields(doctype, mapped)
				if doctype == "UOM":
					mapped["uom_name"] = normalize_uom(mapped.get("uom_name") or record_id)
				if record_id:
					mapped["name"] = record_id
				# Correlation IDs are not document names; Frappe names new documents.

				mapped["doctype"] = doctype
				effective_operation = (
					"UPDATE"
					if mapped.get("name") and frappe.db.exists(doctype, mapped["name"])
					else "CREATE"
				)
				if operation == "DELETE":
					effective_operation = "DELETE"
				_authorize_mobile_write(
					doctype, effective_operation, mapped.get("name"), mapped
				)
				if effective_operation == "DELETE":
					# Deletions must actually delete. Falling through to the
					# update/create branch below would silently resurrect or
					# edit a record the mobile user asked to remove.
					name = mapped.get("name")
					if name and frappe.db.exists(doctype, name):
						frappe.delete_doc(doctype, name, ignore_permissions=True)
						status = "deleted"
					else:
						status = "not_found"
					log_sync(frappe.session.user, doctype, name, operation, status)
					results.append({"status": status, "doctype": doctype, "name": name})
					continue
				if mapped.get("name") and frappe.db.exists(doctype, mapped["name"]):
					doc = frappe.get_doc(doctype, mapped["name"])

					# Conflict check if client provides updatedAt
					client_modified = payload.get("updatedAt")
					if client_modified and not force:
						client_dt = _mobile_datetime(client_modified)
						if doc.modified and doc.modified > client_dt:
							# Log conflict for manual resolution
							try:
								conflict = frappe.get_doc({
									"doctype": "Sync Conflict",
									"doctype_name": doctype,
									"doc_name": doc.name,
									"user": frappe.session.user,
									"mobile_data": json.dumps({
										"modified": client_dt.isoformat(),
										"payload": payload,
									}),
									"server_data": json.dumps({
										"modified": doc.modified.isoformat() if doc.modified else None,
										"doc": doc.as_dict(),
									}),
									"resolution": "Pending",
									"resolved": 0,
								})
								conflict.insert(ignore_permissions=True)
							except Exception:
								frappe.log_error(f"Failed to log conflict for {doctype} {doc.name}")
							log_sync(frappe.session.user, doctype, doc.name, operation, "Conflict")
							results.append({"status": "conflict", "doctype": doctype, "name": doc.name})
							continue

					doc.update(mapped)
					doc.save(ignore_permissions=True)
					name = doc.name
				else:
					doc = frappe.get_doc(mapped)
					doc.insert(ignore_permissions=True)
					name = doc.name

				log_sync(frappe.session.user, doctype, name, operation, "Success")
				results.append({"status": "success", "doctype": doctype, "name": name})
			except Exception as e:
				if doctype == "Field Visit" and "Complete the active Field Visit" in str(e):
					active = frappe.db.exists("Field Visit", {
						"visited_by": frappe.session.user,
						"status": "in_progress",
					})
					results.append({
						"status": "conflict",
						"doctype": doctype,
						"client_id": record.get("clientRecordId") or record.get("recordId"),
						"active_visit": active,
						"error": str(e),
					})
					continue
				results.append({
					"status": "error",
					"store": record.get("storeName") or record.get("store_name"),
					"doctype": locals().get("doctype") or record.get("doctype"),
					"client_id": record.get("clientRecordId") or record.get("recordId"),
					"error": str(e),
				})

		frappe.db.commit()
		return {"success": True, "results": results}
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(f"Push sync data error: {str(e)}")
		return {"success": False, "error": str(e)}
	finally:
		if locals().get("visit_lock"):
			frappe.db.sql("SELECT RELEASE_LOCK(%s)", (visit_lock,))


def _sync_verified_inter_row_spacing():
	"""Publish the verified Pre-flowering average onto its Crop Cycle."""
	if not frappe.get_meta("Crop Cycle").has_field("verified_inter_row_spacing_m"):
		return
	for inspection in frappe.get_all(
		"Inspection",
		filters={"status": "Verified", "inspection_type": "Pre-flowering", "crop_cycle": ["is", "set"]},
		fields=["name", "crop_cycle", "qa_reviewed_on"],
	):
		result = frappe.db.get_value(
			"Inspection Result",
			{"parent": inspection.name, "parenttype": "Inspection", "parameter": "Inter-row Spacing"},
			["measured_value", "observation_count"],
			as_dict=True,
		)
		if not result or result.measured_value is None or cint(result.observation_count) <= 0:
			continue
		current_source = frappe.db.get_value("Crop Cycle", inspection.crop_cycle, "spacing_source_inspection")
		if current_source == inspection.name:
			continue
		frappe.db.set_value(
			"Crop Cycle",
			inspection.crop_cycle,
			{
				"verified_inter_row_spacing_m": flt(result.measured_value),
				"spacing_source_inspection": inspection.name,
				"spacing_verified_on": inspection.qa_reviewed_on or frappe.utils.now_datetime(),
			},
			update_modified=False,
		)

@frappe.whitelist()
def reconcile_mobile_create(store, client_id, payload):
	"""Resolve an uncertain create or create once, serialized by stable mobile ID."""
	import hashlib
	doctype = _resolve_doctype(store, strict=True)
	_require_mobile_doctype(doctype, "write")
	if not client_id or len(str(client_id)) > 140:
		frappe.throw("A valid mobile correlation ID is required.")
	meta = _get_meta(doctype)
	fields = [field for field in ("external_id", ID_FIELD_MAP.get(doctype))
		if field and meta.has_field(field)]
	if not fields:
		frappe.throw(
			_("{0} has no durable mobile correlation field; recovery requires backend configuration.").format(doctype)
		)
	lock = hashlib.sha256((doctype + ":" + str(client_id)).encode()).hexdigest()
	if not frappe.db.sql("SELECT GET_LOCK(%s, 15)", (lock,))[0][0]:
		frappe.throw("A previous create is still running. Retry sync shortly.")
	try:
		names = set()
		for field in fields:
			names.update(frappe.get_all(doctype, filters={field: client_id}, pluck="name"))
		if len(names) > 1:
			frappe.throw("Multiple server records share this mobile ID. Manager reconciliation is required; no new record was created.")
		if names:
			name = next(iter(names))
			if not _mobile_record_is_in_scope(doctype, name=name):
				frappe.throw("The matching record is outside your current assignment. Ask a manager to reconcile it.")
			return {"success": True, "results": [{"status": "success", "doctype": doctype, "name": name}]}
		values = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
		values.pop("name", None)
		values.pop("id", None)
		for field in fields:
			values[field] = client_id
		return push_sync_data([{"storeName": store, "operation": "SYNC", "payload": values}])
	except Exception:
		frappe.db.rollback()
		raise
	finally:
		frappe.db.sql("SELECT RELEASE_LOCK(%s)", (lock,))


def log_sync(user, doctype, doc_name, operation, status, error_message=None):
	"""Helper function to log sync operations"""
	try:
		status_val = _normalize_sync_status(status)
		sync_log = frappe.get_doc({
			"doctype": "Sync Log",
			"user": user,
			"doctype_name": doctype,
			"doc_name": doc_name,
			"operation": operation,
			"status": status_val,
			"error_message": error_message,
			"sync_timestamp": datetime.now()
		})
		sync_log.insert(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(f"Error logging sync: {str(e)}")


def _normalize_sync_status(status):
	if not status:
		return "Success"
	val = str(status).lower()
	if val in ("success", "deleted"):
		return "Success"
	if val in ("conflict",):
		return "Conflict"
	return "Failed"


@frappe.whitelist()
def check_conflicts(doctype, doc_name, mobile_modified):
	"""
	Check if a record has conflicts between mobile and server

	Args:
		doctype: DocType name
		doc_name: Document name
		mobile_modified: Mobile's last modified timestamp

	Returns:
		Conflict status and server data if conflict exists
	"""
	try:
		if not frappe.db.exists(doctype, doc_name):
			return {
				"has_conflict": False,
				"reason": "not_found"
			}

		server_doc = frappe.get_doc(doctype, doc_name)
		server_modified = server_doc.modified

		# Parse mobile modified timestamp
		mobile_modified_dt = _mobile_datetime(mobile_modified)

		# Check if server version is newer
		if server_modified > mobile_modified_dt:
			return {
				"has_conflict": True,
				"server_data": server_doc.as_dict(),
				"server_modified": server_modified.isoformat()
			}

		return {
			"has_conflict": False
		}

	except Exception as e:
		frappe.log_error(f"Check conflicts error: {str(e)}")
		return {
			"has_conflict": False,
			"error": str(e)
		}
