# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate


NUMERIC_DATA_TYPES = {"Number", "Count", "Percent"}


def has_raw_value(row):
	if hasattr(row, "value_captured"):
		return bool(cint(row.value_captured))
	if row.data_type in NUMERIC_DATA_TYPES:
		return row.numeric_value not in (None, "")
	if row.data_type == "Date":
		return bool(row.date_value)
	return bool((row.text_value or "").strip())


def set_agronomy_raw_value(row, value):
	row.value_captured = 0
	row.numeric_value = None
	row.text_value = None
	row.date_value = None
	if value in (None, ""):
		return
	row.value_captured = 1
	if row.data_type in NUMERIC_DATA_TYPES:
		row.numeric_value = value
	elif row.data_type == "Date":
		row.date_value = value
	else:
		text_value = str(value).strip()
		if row.data_type == "Yes/No" and text_value.casefold() in {"yes", "no"}:
			text_value = text_value.title()
		elif row.data_type == "Good/Poor" and text_value.casefold() in {"good", "poor"}:
			text_value = text_value.title()
		elif row.data_type == "Select":
			configured = {
				option.strip().casefold(): option.strip()
				for option in (row.options or "").splitlines()
				if option.strip()
			}
			text_value = configured.get(text_value.casefold(), text_value)
		row.text_value = text_value


def evaluate_agronomy_result(row, window_start_date=None, window_end_date=None):
	if not has_raw_value(row):
		return "Not Evaluated", _("No raw value has been captured.")

	text_value = (row.text_value or "").strip()
	if cint(row.allow_not_applicable) and text_value.lower() in {
		"n/a", "na", "not applicable"
	}:
		return "Not Applicable", _("Marked as not applicable by the field officer.")
	if row.evaluation_mode != "Rule Based":
		return "Informational", _("Recorded for information; no Pass/Fail rule applies.")

	rule = row.comparison_rule
	passed = None
	standard = ""
	if rule == "At Least":
		passed = flt(row.numeric_value) >= flt(row.minimum_value)
		standard = _("at least {0} {1}").format(row.minimum_value, row.unit or "")
	elif rule == "At Most":
		passed = flt(row.numeric_value) <= flt(row.maximum_value)
		standard = _("at most {0} {1}").format(row.maximum_value, row.unit or "")
	elif rule == "Between":
		passed = flt(row.minimum_value) <= flt(row.numeric_value) <= flt(row.maximum_value)
		standard = _("between {0} and {1} {2}").format(
			row.minimum_value, row.maximum_value, row.unit or ""
		)
	elif rule == "Equals":
		if row.data_type in NUMERIC_DATA_TYPES:
			passed = flt(row.numeric_value) == flt(row.expected_value)
		else:
			passed = text_value.casefold() == (row.expected_value or "").strip().casefold()
		standard = _("equal to {0}").format(row.expected_value)
	elif rule == "Expected Value":
		passed = text_value.casefold() == (row.expected_value or "").strip().casefold()
		standard = _("{0}").format(row.expected_value)
	elif rule == "Yes Is Pass":
		passed = text_value.casefold() == "yes"
		standard = _("Yes")
	elif rule == "No Is Pass":
		passed = text_value.casefold() == "no"
		standard = _("No")
	elif rule == "Good Is Pass":
		passed = text_value.casefold() == "good"
		standard = _("Good")
	elif rule == "Poor Is Pass":
		passed = text_value.casefold() == "poor"
		standard = _("Poor")
	elif rule == "Within Report Window":
		if not window_start_date or not window_end_date:
			return "Not Evaluated", _("The report window is not available for date evaluation.")
		passed = getdate(window_start_date) <= getdate(row.date_value) <= getdate(window_end_date)
		standard = _("between {0} and {1}").format(window_start_date, window_end_date)
	else:
		return "Not Evaluated", _("No supported comparison rule is configured.")

	status = "Pass" if passed else "Fail"
	return status, _("{0}; required standard: {1}.").format(status, standard.strip())


class AgronomyReport(Document):
	def before_validate(self):
		self.populate_context()
		self.populate_template_results()
		self.set_week_numbers()
		self.read_geolocation()
		self.set_boundary_status()
		self.evaluate_results()

	def validate(self):
		self.validate_schedule_context()
		self.validate_raw_values()
		self.validate_location()
		if self.docstatus == 0 and self.results:
			self.status = "In Progress" if self.has_recorded_results() else "Scheduled"

	def before_submit(self):
		self.validate_mandatory_results()
		if self.overall_result == "Not Evaluated":
			frappe.throw(_("The report cannot be submitted until its automated result is available."))
		self.status = "Submitted"
		self.submitted_by = frappe.session.user
		self.submitted_at = now_datetime()

	def on_submit(self):
		self.sync_actual_planting_date()
		self.complete_related_stage()
		self.create_corrective_actions()
		self.sync_todo_status("Closed")

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
		self.sync_todo_status("Cancelled")

	def populate_context(self):
		if not self.crop_cycle:
			return
		cycle = frappe.get_doc("Crop Cycle", self.crop_cycle)
		self.production_contract = cycle.production_contract
		self.plot = cycle.plot
		self.crop = cycle.crop
		self.variety = cycle.variety
		self.season = cycle.season
		self.production_category = cycle.production_category
		if cycle.plot:
			plot = frappe.get_doc("Farm Plot", cycle.plot)
			self.outgrower = plot.outgrower
			if plot.outgrower:
				self.assigned_supervisor = frappe.db.get_value(
					"Outgrower", plot.outgrower, "assigned_supervisor"
				)

	def populate_template_results(self):
		if not self.report_template:
			return
		template = frappe.get_doc("Agronomy Report Template", self.report_template)
		self.report_number = template.report_number
		self.stage_name = template.stage_name

		incoming = {}
		for row in self.results or []:
			if row.parameter_code in incoming:
				frappe.throw(_("Parameter {0} is duplicated in the report.").format(row.parameter_code))
			incoming[row.parameter_code] = row

		stored = None
		stored_values = {}
		standard_rows = template.parameters
		use_stored_snapshot = False
		if not self.is_new() and frappe.db.exists(self.doctype, self.name):
			stored = frappe.get_doc(self.doctype, self.name)
			stored_values = {row.parameter_code: row for row in stored.results or []}
			use_stored_snapshot = bool(stored.results) and not self.flags.get(
				"refresh_agronomy_standard_snapshot"
			)
			if use_stored_snapshot:
				standard_rows = stored.results

		if use_stored_snapshot:
			self.template_version = stored.template_version or template.template_version
			self.overall_pass_threshold_percent = (
				stored.overall_pass_threshold_percent
				if stored.overall_pass_threshold_percent not in (None, "")
				else template.overall_pass_threshold_percent
			)
			self.critical_failure_override = stored.critical_failure_override
		else:
			self.template_version = template.template_version
			self.overall_pass_threshold_percent = template.overall_pass_threshold_percent
			self.critical_failure_override = template.critical_failure_override

		self.set("results", [])
		for parameter in standard_rows:
			value_row = incoming.get(parameter.parameter_code) or stored_values.get(
				parameter.parameter_code
			)
			self.append(
				"results",
				{
					"parameter_code": parameter.parameter_code,
					"parameter_label": parameter.parameter_label,
					"section_name": parameter.section_name,
					"data_type": parameter.data_type,
					"options": parameter.options,
					"mandatory": parameter.mandatory,
					"responsible_party": parameter.responsible_party,
					"unit": parameter.unit,
					"template_version": self.template_version,
					"evaluation_mode": parameter.evaluation_mode or "Informational",
					"comparison_rule": parameter.comparison_rule,
					"minimum_value": parameter.minimum_value,
					"maximum_value": parameter.maximum_value,
					"expected_value": parameter.expected_value,
					"severity": parameter.severity or "Standard",
					"weight": parameter.weight or 1,
					"allow_not_applicable": parameter.allow_not_applicable,
					"corrective_action_on_fail": parameter.corrective_action_on_fail,
					"failure_action": parameter.failure_action,
					"corrective_action_due_days": parameter.corrective_action_due_days,
					"value_captured": cint(value_row.value_captured) if value_row else 0,
					"numeric_value": value_row.numeric_value if value_row else None,
					"text_value": value_row.text_value if value_row else None,
					"date_value": value_row.date_value if value_row else None,
					"remarks": value_row.remarks if value_row else None,
				},
			)

	def evaluate_results(self):
		for row in self.results or []:
			row.result_status, row.evaluation_message = evaluate_agronomy_result(
				row, self.window_start_date, self.window_end_date
			)

		evaluated = [row for row in self.results or [] if row.result_status in ("Pass", "Fail")]
		passed = [row for row in evaluated if row.result_status == "Pass"]
		failed = [row for row in evaluated if row.result_status == "Fail"]
		critical_failures = [row for row in failed if row.severity == "Critical"]
		pending_mandatory = [
			row for row in self.results or [] if row.mandatory and not has_raw_value(row)
		]
		total_weight = sum(max(flt(row.weight), 0) for row in evaluated)
		passed_weight = sum(max(flt(row.weight), 0) for row in passed)
		self.evaluated_parameter_count = len(evaluated)
		self.passed_parameter_count = len(passed)
		self.failed_parameter_count = len(failed)
		self.critical_failure_count = len(critical_failures)
		self.pass_percentage = round((passed_weight / total_weight) * 100, 2) if total_weight else 0

		if not evaluated or pending_mandatory:
			self.overall_result = "Not Evaluated"
		elif cint(self.critical_failure_override) and critical_failures:
			self.overall_result = "Fail"
		else:
			self.overall_result = (
				"Pass"
				if flt(self.pass_percentage) >= flt(self.overall_pass_threshold_percent)
				else "Fail"
			)

		corrective_rows = [row for row in failed if row.corrective_action_on_fail]
		self.corrective_action_required = cint(bool(corrective_rows))
		self.corrective_action = "\n".join(
			f"{row.parameter_label}: "
			+ (
				(row.failure_action or "").strip()
				or _("Correct the failed agronomy standard and record completion evidence.")
			)
			for row in corrective_rows
		) or None
		if corrective_rows:
			base_date = self.report_date or nowdate()
			self.corrective_action_due_date = min(
				add_days(base_date, cint(row.corrective_action_due_days or 3))
				for row in corrective_rows
			)
		else:
			self.corrective_action_due_date = None

		self.evaluated_at = now_datetime() if self.has_recorded_results() else None
		self.summary = self.build_automated_summary(failed, pending_mandatory)

	def build_automated_summary(self, failed, pending_mandatory):
		if pending_mandatory:
			return _("Awaiting mandatory raw values for: {0}.").format(
				", ".join(row.parameter_label for row in pending_mandatory)
			)
		if self.overall_result == "Not Evaluated":
			return _("No rule-based agronomy result is currently available.")
		message = _("{0}: {1} of {2} evaluated standards passed ({3}%).").format(
			self.overall_result,
			self.passed_parameter_count,
			self.evaluated_parameter_count,
			self.pass_percentage,
		)
		if failed:
			message += " " + _("Failed standards: {0}.").format(
				", ".join(row.parameter_label for row in failed)
			)
		return message

	def set_week_numbers(self):
		if not self.report_date:
			return
		report_date = getdate(self.report_date)
		self.calendar_week = report_date.isocalendar().week
		planting_date = (
			frappe.db.get_value("Crop Cycle", self.crop_cycle, "planting_date")
			if self.crop_cycle
			else None
		)
		self.planting_week = (
			max(((report_date - getdate(planting_date)).days // 7) + 1, 0)
			if planting_date
			else 0
		)

	def validate_schedule_context(self):
		if self.is_new():
			return
		stored = frappe.db.get_value(
			self.doctype,
			self.name,
			["report_template", "crop_cycle", "stage"],
			as_dict=True,
		)
		for fieldname in ("report_template", "crop_cycle", "stage"):
			if stored and stored.get(fieldname) != self.get(fieldname):
				frappe.throw(
					_("{0} cannot be changed after an Agronomy Report has been scheduled.").format(
						self.meta.get_label(fieldname)
					)
				)

	def validate_raw_values(self):
		for row in self.results or []:
			if not has_raw_value(row):
				row.numeric_value = None
				row.text_value = None
				row.date_value = None
				continue
			raw_value = (
				row.numeric_value
				if row.data_type in NUMERIC_DATA_TYPES
				else row.date_value
				if row.data_type == "Date"
				else row.text_value
			)
			set_agronomy_raw_value(row, raw_value)
			text_value = (row.text_value or "").strip()
			if cint(row.allow_not_applicable) and text_value.casefold() in {
				"n/a", "na", "not applicable"
			}:
				continue
			if row.data_type == "Percent" and not 0 <= flt(row.numeric_value) <= 100:
				frappe.throw(_("{0} must be between 0 and 100 percent.").format(row.parameter_label))
			if row.data_type == "Count" and (
				flt(row.numeric_value) < 0 or flt(row.numeric_value) != cint(row.numeric_value)
			):
				frappe.throw(_("{0} must be a non-negative whole-number count.").format(row.parameter_label))
			if row.data_type == "Yes/No" and text_value.casefold() not in {"yes", "no"}:
				frappe.throw(_("{0} must be Yes or No.").format(row.parameter_label))
			if row.data_type == "Good/Poor" and text_value.casefold() not in {"good", "poor"}:
				frappe.throw(_("{0} must be Good or Poor.").format(row.parameter_label))
			if row.data_type == "Select":
				options = {
					value.strip().casefold()
					for value in (row.options or "").splitlines()
					if value.strip()
				}
				if options and text_value.casefold() not in options:
					frappe.throw(
						_("{0} must be one of the configured values.").format(row.parameter_label)
					)

	def read_geolocation(self):
		if not self.location:
			return
		try:
			geo = json.loads(self.location) if isinstance(self.location, str) else self.location
			coordinates = geo.get("features", [])[0].get("geometry", {}).get("coordinates", [])
			if len(coordinates) >= 2:
				self.longitude = coordinates[0]
				self.latitude = coordinates[1]
		except (AttributeError, IndexError, TypeError, ValueError):
			frappe.throw(_("Location Map contains invalid GeoJSON."))

	def set_boundary_status(self):
		if self.latitude in (None, "") or self.longitude in (None, "") or not self.plot:
			return
		vertices = frappe.get_all(
			"Plot Vertex",
			filters={"parent": self.plot, "parenttype": "Farm Plot", "parentfield": "polygon"},
			fields=["latitude", "longitude"],
			order_by="order_index asc, idx asc",
		)
		if len(vertices) < 3:
			self.inside_plot_boundary = 1
			return
		self.inside_plot_boundary = point_inside_polygon(
			flt(self.latitude),
			flt(self.longitude),
			[(flt(row.latitude), flt(row.longitude)) for row in vertices],
		)

	def validate_location(self):
		if self.flags.get("ignore_agronomy_location_validation"):
			return
		if self.docstatus == 0 and self.latitude in (None, "") and self.longitude in (None, ""):
			return
		if self.latitude in (None, "") or not -90 <= flt(self.latitude) <= 90:
			frappe.throw(_("Enter a valid report latitude."))
		if self.longitude in (None, "") or not -180 <= flt(self.longitude) <= 180:
			frappe.throw(_("Enter a valid report longitude."))
		if flt(self.gps_accuracy_meters) <= 0:
			frappe.throw(_("GPS Accuracy must be greater than zero."))
		maximum_accuracy = flt(
			frappe.db.get_single_value("FieldOps Settings", "maximum_gps_accuracy_m") or 5
		)
		if self.docstatus == 1 and flt(self.gps_accuracy_meters) > maximum_accuracy:
			frappe.throw(
				_("GPS accuracy must be {0} m or better before submission.").format(
					maximum_accuracy
				)
			)
		if self.docstatus == 1 and not cint(self.inside_plot_boundary):
			frappe.throw(_("The agronomy report location must be inside the Farm Plot boundary."))

	def has_recorded_results(self):
		return any(has_raw_value(row) for row in self.results)

	def validate_mandatory_results(self):
		missing = []
		for row in self.results:
			if not row.mandatory:
				continue
			if not has_raw_value(row):
				missing.append(row.parameter_label)
		if missing:
			frappe.throw(
				_("Complete all mandatory report parameters: {0}.").format(", ".join(missing))
			)

	def sync_actual_planting_date(self):
		if self.stage_name != "Planting" and cint(self.report_number) != 2:
			return

		actual_planting_date = next(
			(
				row.date_value
				for row in self.results
				if row.parameter_code == "PLANTING_DATE" and row.date_value
			),
			None,
		)
		if not actual_planting_date:
			frappe.throw(_("Actual Planting Date is required on the Planting Agronomy Report."))

		if self.production_contract:
			frappe.db.set_value(
				"Outgrower Production Contract",
				self.production_contract,
				"actual_planting_date",
				actual_planting_date,
			)

		if not self.crop_cycle:
			return

		cycle = frappe.get_doc("Crop Cycle", self.crop_cycle)
		if cycle.planting_date and getdate(cycle.planting_date) == getdate(actual_planting_date):
			return

		frappe.db.set_value(
			"Crop Cycle",
			cycle.name,
			{
				"planting_date": actual_planting_date,
				"start_date": actual_planting_date,
			},
		)
		cycle.planting_date = actual_planting_date
		cycle.start_date = actual_planting_date

		from naseco_fieldopsbackend.inspection_scheduler import sync_crop_cycle_lifecycle

		sync_crop_cycle_lifecycle(cycle)

	def complete_related_stage(self):
		if not self.stage:
			return
		mandatory = frappe.get_all(
			"Stage Activity",
			filters={"stage": self.stage, "mandatory": 1, "status": ["!=", "Cancelled"]},
			fields=["status"],
		)
		all_activities_complete = all(row.status == "Completed" for row in mandatory)
		frappe.db.set_value(
			"Crop Cycle Stage",
			self.stage,
			{
				"status": "Completed" if all_activities_complete else "In Progress",
				"completion_percentage": 100 if all_activities_complete else 90,
				"mandatory_activity_count": len(mandatory),
				"completed_activity_count": len(
					[row for row in mandatory if row.status == "Completed"]
				),
			},
			update_modified=False,
		)
		from naseco_fieldopsbackend.inspection_scheduler import update_crop_cycle_current_stage

		update_crop_cycle_current_stage(self.crop_cycle)

	def create_corrective_actions(self):
		failed = [
			row
			for row in self.results
			if row.result_status == "Fail"
			and row.corrective_action_on_fail
		]
		for row in failed:
			parameter_code = row.parameter_code
			if frappe.db.exists(
				"Field Corrective Action",
				{
					"source_type": "Agronomy Report",
					"source_name": self.name,
					"source_parameter": parameter_code,
				},
			):
				continue
			frappe.get_doc(
				{
					"doctype": "Field Corrective Action",
					"source_type": "Agronomy Report",
					"source_name": self.name,
					"source_parameter": parameter_code,
					"agronomy_report": self.name,
					"crop_cycle": self.crop_cycle,
					"plot": self.plot,
					"outgrower": self.outgrower,
					"responsible_party": row.responsible_party,
					"assigned_to": self.assigned_supervisor,
					"due_date": add_days(
						self.report_date or nowdate(), cint(row.corrective_action_due_days or 3)
					),
					"description": (row.failure_action or "").strip()
					or _("Resolve failed agronomy parameter: {0}").format(row.parameter_label),
				}
			).insert(ignore_permissions=True)

	def sync_todo_status(self, status):
		for todo in frappe.get_all(
			"ToDo",
			filters={"reference_type": self.doctype, "reference_name": self.name},
			pluck="name",
		):
			frappe.db.set_value("ToDo", todo, "status", status, update_modified=False)


@frappe.whitelist()
def get_agronomy_observation_schema(report):
	doc = frappe.get_doc("Agronomy Report", report)
	doc.check_permission("read")
	return {
		"report": doc.name,
		"status": doc.status,
		"overall_result": doc.overall_result,
		"attributes": [
			{
				"parameter_code": row.parameter_code,
				"label": row.parameter_label,
				"section": row.section_name or _("Observations"),
				"data_type": row.data_type,
				"options": [
					value.strip()
					for value in (row.options or "").splitlines()
					if value.strip()
				],
				"unit": row.unit,
				"mandatory": cint(row.mandatory),
				"value": (
					row.numeric_value
					if row.data_type in NUMERIC_DATA_TYPES
					else row.date_value
					if row.data_type == "Date"
					else row.text_value
				)
				if has_raw_value(row)
				else None,
				"remarks": row.remarks,
				"result_status": row.result_status,
			}
			for row in doc.results or []
		],
	}


@frappe.whitelist()
def save_agronomy_observations(report, observations):
	frappe.db.sql("select name from `tabAgronomy Report` where name = %s for update", report)
	doc = frappe.get_doc("Agronomy Report", report)
	doc.check_permission("write")
	if doc.docstatus != 0 or doc.status in ("Submitted", "Cancelled"):
		frappe.throw(_("Observations can only be changed on an open Agronomy Report."))

	observations = frappe.parse_json(observations) if isinstance(observations, str) else observations
	provided = {}
	for observation in observations or []:
		parameter_code = observation.get("parameter_code")
		if not parameter_code:
			continue
		if parameter_code in provided:
			frappe.throw(_("Parameter {0} was supplied more than once.").format(parameter_code))
		provided[parameter_code] = observation

	results = {row.parameter_code: row for row in doc.results or []}
	unknown = sorted(set(provided) - set(results))
	if unknown:
		frappe.throw(_("Unknown Agronomy Report parameters: {0}.").format(", ".join(unknown)))
	for parameter_code, observation in provided.items():
		row = results[parameter_code]
		set_agronomy_raw_value(row, observation.get("value"))
		row.remarks = (observation.get("remarks") or "").strip() or None

	doc.save()
	return {
		"report": doc.name,
		"status": doc.status,
		"overall_result": doc.overall_result,
		"pass_percentage": doc.pass_percentage,
		"evaluated_parameter_count": doc.evaluated_parameter_count,
		"failed_parameter_count": doc.failed_parameter_count,
		"corrective_action_required": doc.corrective_action_required,
	}


def point_inside_polygon(latitude, longitude, polygon):
	x, y = longitude, latitude
	inside = False
	j = len(polygon) - 1
	for i in range(len(polygon)):
		yi, xi = polygon[i]
		yj, xj = polygon[j]
		if ((yi > y) != (yj > y)) and (
			x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
		):
			inside = not inside
		j = i
	return cint(inside)
