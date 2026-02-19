# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from datetime import datetime

# Mobile <-> Frappe mappings
BASE_STORE_TO_DOCTYPE = {
	"outgrowers": "Outgrower",
	"plots": "Farm Plot",
	"crop_cycles": "Crop Cycle",
	"crop_cycle_stages": "Crop Cycle Stage",
	"visits": "Field Visit",
	"findings": "Finding",
	"plot_crop_assignments": "Plot Crop Assignment",
	"plot_assignments": "Plot Crop Assignment",
	"stage_activities": "Stage Activity",
	"stage_input_requests": "Stage Input Request",
	"stage_input_dispatches": "Stage Input Dispatch",
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
	"units": "Unit",
	"inspection_attributes": "Inspection Attribute",
}

STORE_TO_DOCTYPE = dict(BASE_STORE_TO_DOCTYPE)
STORE_TO_DOCTYPE.update({
	"OutGrower": "Outgrower",
	"Plot": "Farm Plot",
	"CropCycle": "Crop Cycle",
	"CropCycleStage": "Crop Cycle Stage",
	"Visit": "Field Visit",
	"PlotCropAssignment": "Plot Crop Assignment",
	"StageActivity": "Stage Activity",
	"StageInputRequest": "Stage Input Request",
	"StageInputDispatch": "Stage Input Dispatch",
	"Crop": "Crop",
	"Variety": "Crop Variety",
	"Season": "Season",
	"CropRecipe": "Crop Recipe",
	"RecipeStage": "Recipe Stage",
	"RecipeInput": "Recipe Input Item",
	"VisitType": "Visit Type",
	"Region": "Region",
	"Unit": "Unit",
	"InspectionAttribute": "Inspection Attribute",
})

DOCTYPE_TO_STORE = {v: k for k, v in BASE_STORE_TO_DOCTYPE.items()}

ID_FIELD_MAP = {
	"Outgrower": "outgrower_id",
	"Farm Plot": "plot_id",
	"Crop Cycle": "crop_cycle_id",
	"Crop Cycle Stage": "stage_id",
	"Field Visit": "visit_id",
	"Finding": "finding_id",
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
		"outgrowerType": "outgrower_type",
	},
	"Farm Plot": {
		"plotId": "plot_id",
		"outgrowerId": "outgrower",
		"plotName": "plot_name",
		"plotType": "plot_type",
		"areaAcres": "area_acres",
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
	},
	"Season": {
		"seasonId": "season_id",
		"seasonName": "season_name",
	},
	"Crop Cycle": {
		"cropCycleId": "crop_cycle_id",
		"plotId": "plot",
		"cropId": "crop",
		"varietyId": "variety",
		"seasonId": "season",
		"startDate": "start_date",
		"expectedHarvestDate": "expected_harvest_date",
		"currentStageId": "current_stage",
		"nextInspectionDate": "next_inspection_date",
	},
	"Crop Cycle Stage": {
		"stageId": "stage_id",
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
	},
	"Finding": {
		"findingId": "finding_id",
		"visitId": "visit",
		"cropCycleId": "crop_cycle",
		"stageId": "stage",
	},
	"Stage Activity": {
		"activityId": "activity_id",
		"cropCycleId": "crop_cycle",
		"stageId": "stage",
		"visitId": "visit",
		"activityDate": "activity_date",
		"durationHours": "duration_hours",
	},
	"Stage Input Request": {
		"requestId": "request_id",
		"cropCycleId": "crop_cycle",
		"stageId": "stage",
		"inputType": "input_type",
		"quantity": "quantity",
		"requestedDate": "requested_date",
	},
	"Stage Input Dispatch": {
		"dispatchId": "dispatch_id",
		"cropCycleId": "crop_cycle",
		"stageId": "stage",
		"inputType": "input_type",
		"quantity": "quantity",
		"dispatchDate": "dispatch_date",
		"requestId": "request_id",
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
		"quantityPerAcre": "quantity_per_acre",
	},
	"Visit Type": {
		"visitTypeId": "visit_type_id",
		"name": "type_name",
	},
	"Region": {
		"name": "region_name",
	},
	"Unit": {
		"unitName": "unit_name",
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
		"applicationId": "application_id",
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
		"advanceId": "advance_id",
		"postingDate": "posting_date",
		"purpose": "purpose",
		"amount": "advance_amount",
		"repayFromSalary": "repay_from_salary",
		"status": "status",
		"attachments": "attachments_json",
	},
	"Expense Claim": {
		"expenseId": "expense_id",
		"dateSubmitted": "date_submitted",
		"amount": "total_claimed_amount",
		"category": "category",
		"status": "status",
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


def _map_mobile_to_doc(doctype, payload):
	if doctype == "Outgrower":
		payload = _normalize_outgrower_payload(payload)

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
				for inp in stage.get("inputsPerAcre", []) or []:
					inputs.append({
						"input_type": inp.get("type"),
						"input_name": inp.get("name"),
						"quantity_per_acre": inp.get("quantityPerAcre"),
						"unit": inp.get("unit"),
					})
				stage_doc["inputs"] = inputs
				result["stages"].append(stage_doc)
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


def _map_doc_to_mobile(doctype, doc_dict):
	mapping = MOBILE_FIELD_MAP.get(doctype, {})
	reverse = {v: k for k, v in mapping.items()}
	result = {}
	for key, value in (doc_dict or {}).items():
		if key in ("doctype", "owner", "modified_by", "docstatus", "idx", "parent", "parenttype", "parentfield"):
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
				for inp in s.get("inputs", []) or []:
					inputs.append({
						"type": inp.get("input_type"),
						"name": inp.get("input_name"),
						"quantityPerAcre": inp.get("quantity_per_acre"),
						"unit": inp.get("unit"),
					})
				stage["inputsPerAcre"] = inputs
				stages.append(stage)
			result["stages"] = stages
			continue

		result[reverse.get(key, key)] = value

	# ensure id fields returned
	if doctype in ID_FIELD_MAP and ID_FIELD_MAP[doctype] in doc_dict:
		mobile_id_field = _reverse_id_field_name(doctype)
		if mobile_id_field:
			result[mobile_id_field] = doc_dict.get(ID_FIELD_MAP[doctype])
	if doctype == "Outgrower":
		_enrich_outgrower_aliases(result)
	return result


def _reverse_id_field_name(doctype):
	for mobile_field, frappe_field in MOBILE_FIELD_MAP.get(doctype, {}).items():
		if frappe_field == ID_FIELD_MAP.get(doctype):
			return mobile_field
	return None


def _resolve_doctype(store_or_doctype):
	if store_or_doctype in STORE_TO_DOCTYPE:
		return STORE_TO_DOCTYPE.get(store_or_doctype)
	if isinstance(store_or_doctype, str):
		key = store_or_doctype.lower()
		if key in STORE_TO_DOCTYPE:
			return STORE_TO_DOCTYPE.get(key)
	return store_or_doctype


_meta_cache = {}


def _get_meta(doctype):
	if doctype not in _meta_cache:
		_meta_cache[doctype] = frappe.get_meta(doctype)
	return _meta_cache[doctype]


def _filter_fields(doctype, data):
	meta = _get_meta(doctype)
	valid_fields = {df.fieldname for df in meta.fields}
	valid_fields.update({"doctype", "name"})
	return {k: v for k, v in data.items() if k in valid_fields}


def _resolve_employee_fields(doctype, payload, result):
	meta = _get_meta(doctype)
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
	def _vals(keys):
		out = []
		for key in keys:
			out.extend(_as_list(args.get(key)))
		return [v for v in out if v]

	def _resolve_by_email(values):
		if not values:
			return set()
		rows = frappe.get_all("Employee", filters={"user_id": ["in", list(set(values))]}, fields=["name"])
		return {r.name for r in rows}

	def _resolve_by_name(values):
		if not values:
			return set()
		rows = frappe.get_all("Employee", filters={"employee_name": ["in", list(set(values))]}, fields=["name"])
		return {r.name for r in rows}

	source_sets = []

	# 1) Explicit employee ids
	explicit_ids = _vals(("attendance_employee_id", "attendance_employee", "employee_id"))
	if explicit_ids:
		valid_ids = {emp for emp in explicit_ids if frappe.db.exists("Employee", emp)}
		source_sets.append(valid_ids)

	# 2) Email fields (attendance-specific first, then legacy fallback)
	attendance_emails = _vals(("attendance_user_email", "attendance_user", "attendance_user_id"))
	legacy_emails = _vals(("user_email", "user_id"))
	email_values = attendance_emails or legacy_emails
	if not email_values:
		# assigned_to is a final legacy fallback only
		email_values = _vals(("assigned_to",))
	if email_values:
		source_sets.append(_resolve_by_email(email_values))

	# 3) Full name fields
	full_names = _vals(("attendance_employee_name", "full_name"))
	if full_names:
		source_sets.append(_resolve_by_name(full_names))

	# Optional fallback to current logged-in user email
	if not source_sets and getattr(frappe.session, "user", None) and frappe.session.user not in ("Guest", "Administrator"):
		source_sets.append(_resolve_by_email([frappe.session.user]))

	if not source_sets:
		return []

	# Strict combination: intersection of all provided identity sources
	resolved = source_sets[0]
	for s in source_sets[1:]:
		resolved = resolved.intersection(s)

	return sorted(resolved)


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
		emails = _get_identity_emails(args)
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

				doctype = record.get("doctype")
				operation = (record.get("operation") or "").upper()
				doc_data = record.get("doc") or {}
				if doctype == "Outgrower":
					doc_data = _normalize_outgrower_payload(doc_data)

				result = {"doctype": doctype, "operation": operation, "status": "success"}

				if operation == "CREATE":
					doc = frappe.get_doc(doc_data)
					doc.insert(ignore_permissions=True)
					result["name"] = doc.name
				elif operation == "UPDATE":
					doc_name = doc_data.get("name")
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
					doc_name = doc_data.get("name")
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
			"Field Visit", "Finding", "Plot Crop Assignment", "Stage Activity",
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

		modified_records = {}

		for doctype in target_doctypes:
			try:
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
						full_records.append(doc_dict)
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
			"Unit": ["*"],
			"Inspection Attribute": ["*"],
			"Crop Cycle Stage": ["*"]
		}

		for doctype, fields in reference_doctypes.items():
			try:
				records = frappe.get_all(doctype, fields=fields)
				reference_data[doctype] = records
			except Exception as e:
				frappe.log_error(f"Error fetching reference {doctype}: {str(e)}")

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
def get_sync_data(last_sync=None, officer_region=None, **kwargs):
	"""
	Get all synced data since last_sync. Returns data grouped by store name.
	"""
	try:
		args = _get_request_args(kwargs)
		if last_sync:
			last_sync_dt = datetime.fromisoformat(str(last_sync).replace('Z', '+00:00'))
		else:
			last_sync_dt = None

		# Main synced doctypes
		sync_doctypes = [
			"Outgrower",
			"Farm Plot",
			"Crop Cycle",
			"Crop Cycle Stage",
			"Field Visit",
			"Finding",
			"Plot Crop Assignment",
			"Stage Activity",
			"Stage Input Request",
			"Stage Input Dispatch",
			"Attendance",
			"Employee Checkin",
			"Expense Claim",
			"Leave Application",
			"Employee Advance",
		]

		# Reference doctypes (always include)
		reference_doctypes = [
			"Crop",
			"Crop Variety",
			"Season",
			"Crop Recipe",
			"Visit Type",
			"Region",
			"Unit",
			"Inspection Attribute",
			"Crop Cycle Stage",
		]

		data = {}

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
			elif last_sync_dt:
				filters.append(["modified", ">", last_sync_dt])

			if officer_region and doctype == "Outgrower":
				filters.append(["region", "=", officer_region])
			if officer_region and doctype == "Farm Plot" and region_outgrowers:
				filters.append(["outgrower", "in", region_outgrowers])

			records = frappe.get_all(doctype, filters=filters, fields=["name"], order_by="modified asc")
			full_docs = []
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
				records = frappe.get_all(doctype, fields=["name"], order_by="modified asc")
				full_docs = [
					_map_doc_to_mobile(doctype, frappe.get_doc(doctype, row.name).as_dict())
					for row in records
				]
				store = DOCTYPE_TO_STORE.get(doctype, doctype)
				data[store] = full_docs
			except Exception as e:
				frappe.log_error(f"Error fetching reference {doctype}: {str(e)}")

		return {
			"data": data,
			"server_time": datetime.now().isoformat(),
			"last_sync": last_sync,
		}
	except Exception as e:
		frappe.log_error(f"Get sync data error: {str(e)}")
		return {"error": str(e)}


@frappe.whitelist()
def push_sync_data(data):
	"""
	Create/update records pushed from mobile app.
	"""
	try:
		records = json.loads(data) if isinstance(data, str) else data
		if isinstance(records, dict) and "data" in records:
			records = records.get("data")

		results = []
		for record in records or []:
			try:
				store = record.get("storeName") or record.get("store_name") or record.get("doctype")
				doctype = _resolve_doctype(store)
				payload = record.get("payload") or record.get("doc") or {}
				if doctype == "Outgrower":
					payload = _normalize_outgrower_payload(payload)
				operation = (record.get("operation") or "SYNC").upper()
				record_id = record.get("recordId") or payload.get("id") or payload.get("name")
				force = record.get("force") or payload.get("force")

				if operation == "DELETE":
					if record_id and frappe.db.exists(doctype, record_id):
						frappe.delete_doc(doctype, record_id, ignore_permissions=True)
					log_sync(frappe.session.user, doctype, record_id, "DELETE", "Success")
					results.append({"status": "deleted", "doctype": doctype, "name": record_id})
					continue

				mapped = _map_mobile_to_doc(doctype, payload)
				if record_id:
					mapped["name"] = record_id
				elif ID_FIELD_MAP.get(doctype) and mapped.get(ID_FIELD_MAP[doctype]):
					mapped["name"] = mapped[ID_FIELD_MAP[doctype]]

				mapped["doctype"] = doctype
				if mapped.get("name") and frappe.db.exists(doctype, mapped["name"]):
					doc = frappe.get_doc(doctype, mapped["name"])

					# Conflict check if client provides updatedAt
					client_modified = payload.get("updatedAt")
					if client_modified and not force:
						client_dt = datetime.fromisoformat(str(client_modified).replace('Z', '+00:00'))
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
				results.append({"status": "error", "doctype": record.get("doctype"), "error": str(e)})

		frappe.db.commit()
		return {"success": True, "results": results}
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(f"Push sync data error: {str(e)}")
		return {"success": False, "error": str(e)}

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
		mobile_modified_dt = datetime.fromisoformat(mobile_modified.replace('Z', '+00:00'))

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
