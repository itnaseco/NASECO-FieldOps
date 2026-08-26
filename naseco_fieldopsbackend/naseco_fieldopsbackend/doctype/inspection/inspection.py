# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import json
import math
import statistics
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, now_datetime


PASS_STATUSES = {"Pass", "Good"}
FAIL_STATUSES = {"Fail", "Poor", "Corrective Action Required", "Auto Reject"}
NUMERIC_DATA_TYPES = {"Number", "Count", "Percent", "Score"}
LEGACY_PERCENTAGE_PROTOCOL = "Legacy Percentage V1"
CUMULATIVE_COUNTS_PROTOCOL = "Cumulative Counts V2"
POSITIONING_DEFAULTS = {
	"target_take_spacing_m": 5.0,
	"minimum_take_spacing_m": 3.0,
	"maximum_take_spacing_m": 7.0,
	"minimum_spacing_compliance_percent": 80.0,
	"preferred_gps_accuracy_m": 3.0,
	"maximum_gps_accuracy_m": 5.0,
	"minimum_location_samples": 3,
	"location_capture_timeout_seconds": 30,
	"maximum_location_age_seconds": 60,
	"allow_positioning_override": 1,
	"positioning_override_role": "System Manager",
}
STANDARD_FIELDS = [
	"name",
	"parameter",
	"mandatory",
	"comparison_rule",
	"aggregation_method",
	"minimum_value",
	"maximum_value",
	"expected_text",
	"unit",
	"good_label",
	"poor_label",
	"auto_reject_on_fail",
	"corrective_action_on_fail",
	"standard_notes",
]


def get_positioning_settings():
	settings = frappe._dict(POSITIONING_DEFAULTS.copy())
	try:
		if frappe.db.exists("DocType", "FieldOps Settings"):
			doc = frappe.get_cached_doc("FieldOps Settings")
			for fieldname in POSITIONING_DEFAULTS:
				value = doc.get(fieldname)
				if value not in (None, ""):
					settings[fieldname] = value
	except frappe.DoesNotExistError:
		pass

	for fieldname in (
		"target_take_spacing_m",
		"minimum_take_spacing_m",
		"maximum_take_spacing_m",
		"minimum_spacing_compliance_percent",
		"preferred_gps_accuracy_m",
		"maximum_gps_accuracy_m",
	):
		settings[fieldname] = flt(settings[fieldname])
	for fieldname in (
		"minimum_location_samples",
		"location_capture_timeout_seconds",
		"maximum_location_age_seconds",
		"allow_positioning_override",
	):
		settings[fieldname] = cint(settings[fieldname])
	return settings


def get_positioning_issues(
	settings,
	gps_accuracy_meters,
	location_sample_count,
	location_age_seconds,
	distance_from_previous_take_m=None,
	inside_plot_boundary=True,
):
	issues = []
	accuracy = flt(gps_accuracy_meters)
	if accuracy <= 0:
		issues.append(_("GPS accuracy is required."))
	elif accuracy > settings.maximum_gps_accuracy_m:
		issues.append(
			_("GPS accuracy is {0} m; it must be {1} m or better.").format(
				round(accuracy, 1),
				settings.maximum_gps_accuracy_m,
			)
		)

	sample_count = cint(location_sample_count)
	if sample_count < settings.minimum_location_samples:
		issues.append(
			_("Only {0} stable GPS sample(s) were captured; at least {1} are required.").format(
				sample_count,
				settings.minimum_location_samples,
			)
		)

	if location_age_seconds is None or abs(flt(location_age_seconds)) > settings.maximum_location_age_seconds:
		issues.append(
			_("The selected GPS fix is not within the allowed {0}-second capture window.").format(
				settings.maximum_location_age_seconds
			)
		)

	if distance_from_previous_take_m is not None:
		distance = flt(distance_from_previous_take_m)
		if distance < settings.minimum_take_spacing_m:
			issues.append(
				_("This take is {0} m from the previous take; move at least {1} m away.").format(
					round(distance, 1),
					settings.minimum_take_spacing_m,
				)
			)
		elif distance > settings.maximum_take_spacing_m:
			issues.append(
				_("This take is {0} m from the previous take; move within {1} m.").format(
					round(distance, 1),
					settings.maximum_take_spacing_m,
				)
			)

	if not inside_plot_boundary:
		issues.append(_("The captured location is outside the farm plot boundary."))
	return issues


def can_override_positioning(settings=None):
	settings = settings or get_positioning_settings()
	if not settings.allow_positioning_override:
		return False
	if frappe.session.user == "Administrator":
		return True
	return settings.positioning_override_role in frappe.get_roles(frappe.session.user)


def calculate_cumulative_incidence(readings, takes_by_number):
	take_numbers = {cint(row.take_number) for row in readings}
	observed_count = sum(
		cint(
			row.observed_count
			if getattr(row, "observed_count", None) not in (None, "")
			else row.measured_value
		)
		for row in readings
	)
	total_plants = sum(
		cint(takes_by_number[take_number].total_plants_counted)
		for take_number in take_numbers
		if take_number in takes_by_number
	)
	incidence = (observed_count / total_plants) * 100 if total_plants > 0 else None
	return observed_count, total_plants, incidence


def is_cumulative_count_standard(standard, sampling_protocol_version):
	return bool(
		sampling_protocol_version == CUMULATIVE_COUNTS_PROTOCOL
		and standard.calculation_method == "Cumulative Incidence"
	)


def is_take_value_mandatory(standard, sampling_protocol_version):
	return bool(
		standard.mandatory
		and not is_cumulative_count_standard(standard, sampling_protocol_version)
	)


class Inspection(Document):
	def validate(self):
		self.ensure_completed_inspection_is_immutable()
		self.validate_quality_inspector()
		self.populate_context()
		standards = self.get_standards()
		self.ensure_cumulative_count_results(standards)
		self.evaluate_take_results(standards)
		self.evaluate_inspection_observations(standards)
		self.calculate_take_positioning()
		self.validate_new_take_positioning()
		self.calculate_take_completion(standards)
		self.calculate_inspection_control_completion(standards)
		self.aggregate_results(standards)
		self.calculate_compliance()
		self.calculate_inspection_quality()
		self.complete_if_all_takes_done()
		self.calculate_certification_totals()
		self.validate_completion()

	def on_update(self):
		if self.status in ("Awaiting QA Review", "Verified"):
			self.create_corrective_actions()

	def on_trash(self):
		if self.status in ("Awaiting QA Review", "Verified", "Reinspection Required"):
			frappe.throw(
				_("Completed Inspections cannot be deleted."),
				title=_("Inspection Is Locked"),
			)

	def ensure_completed_inspection_is_immutable(self):
		if self.is_new() or self.flags.get("allow_completed_update"):
			return
		stored_status = frappe.db.get_value("Inspection", self.name, "status")
		if stored_status in ("Awaiting QA Review", "Verified", "Reinspection Required"):
			frappe.throw(
				_("Inspection {0} is completed and can no longer be edited.").format(
					frappe.bold(self.name)
				),
				title=_("Inspection Is Locked"),
			)

	def populate_context(self):
		self.sampling_protocol_version = (
			self.sampling_protocol_version or CUMULATIVE_COUNTS_PROTOCOL
		)
		if not self.crop_cycle:
			return

		cycle = frappe.get_doc("Crop Cycle", self.crop_cycle)
		self.production_contract = cycle.production_contract
		self.plot = self.plot or cycle.plot
		self.crop = self.crop or cycle.crop
		self.season = self.season or cycle.season
		self.production_category = self.production_category or cycle.production_category
		self.seed_class = self.seed_class or cycle.seed_class

		if self.plot:
			plot = frappe.get_doc("Farm Plot", self.plot)
			self.outgrower = self.outgrower or plot.outgrower
			self.plot_area_hectares = round((plot.area_acres or 0) * 0.404686, 3)

		counts_per_hectare = 4
		if self.inspection_template:
			template = frappe.get_doc("Inspection Template", self.inspection_template)
			self.inspection_type = self.inspection_type or template.inspection_type
			counts_per_hectare = template.counts_per_hectare or counts_per_hectare

		self.required_take_count = max(1, math.ceil((self.plot_area_hectares or 0) * counts_per_hectare))

	def validate_quality_inspector(self):
		if self.assigned_to and "Quality Inspector" not in frappe.get_roles(self.assigned_to):
			frappe.throw(
				_("{0} must have the Quality Inspector role.").format(
					frappe.bold(self.assigned_to)
				)
			)

	def get_standards(self):
		if not self.inspection_template or not self.production_category:
			return []

		filters = {
			"inspection_template": self.inspection_template,
			"production_category": self.production_category,
		}
		if self.seed_class:
			filters["seed_class"] = self.seed_class
		standards = frappe.get_all(
			"Inspection Standard", filters=filters, fields=STANDARD_FIELDS,
			order_by="creation asc, parameter asc",
		)
		if not standards and self.seed_class:
			# Category-wide standards remain valid until class-specific rules are configured.
			filters["seed_class"] = ["is", "not set"]
			standards = frappe.get_all(
				"Inspection Standard", filters=filters, fields=STANDARD_FIELDS,
				order_by="creation asc, parameter asc",
			)
		for standard in standards:
			parameter = frappe.db.get_value(
				"Inspection Parameter",
				standard.parameter,
				[
					"parameter_name",
					"data_type",
					"unit",
					"applies_to",
					"measurement_scope",
					"calculation_method",
					"denominator_basis",
					"requires_take_counts",
					"description",
				],
				as_dict=True,
			)
			standard.parameter_name = parameter.parameter_name if parameter else standard.parameter
			standard.data_type = parameter.data_type if parameter else "Number"
			standard.responsibility = parameter.applies_to if parameter else "Both"
			standard.measurement_scope = (
				parameter.measurement_scope if parameter else "Inspection Take"
			)
			standard.calculation_method = (
				parameter.calculation_method if parameter else "Direct Value"
			)
			standard.denominator_basis = parameter.denominator_basis if parameter else None
			standard.requires_take_counts = cint(parameter.requires_take_counts) if parameter else 0
			standard.description = parameter.description if parameter else None
			standard.unit = standard.unit or (parameter.unit if parameter else None)
			if is_cumulative_count_standard(standard, self.sampling_protocol_version):
				standard.data_type = "Count"
				standard.unit = (parameter.unit if parameter else None) or "Nos"
			if self.sampling_protocol_version == LEGACY_PERCENTAGE_PROTOCOL:
				standard.measurement_scope = "Inspection Take"
				if standard.calculation_method == "Cumulative Incidence":
					standard.calculation_method = "Direct Value"
					standard.data_type = "Percent"
					standard.unit = "Percent"
					if standard.aggregation_method == "Cumulative Incidence":
						standard.aggregation_method = "Worst Case"
			standard.aggregation_method = self.resolve_aggregation_method(standard)
		return standards

	def ensure_cumulative_count_results(self, standards):
		if self.sampling_protocol_version != CUMULATIVE_COUNTS_PROTOCOL:
			return

		count_standards = [
			row
			for row in standards
			if row.measurement_scope != "Inspection"
			and is_cumulative_count_standard(row, self.sampling_protocol_version)
		]
		if not count_standards:
			return

		existing = {
			(cint(row.take_number), row.parameter) for row in self.take_results or []
		}
		for take in self.takes or []:
			if cint(take.total_plants_counted) <= 0:
				continue
			for standard in count_standards:
				key = (cint(take.take_number), standard.parameter)
				if key in existing:
					continue
				self.append(
					"take_results",
					{
						"take_number": take.take_number,
						"parameter": standard.parameter,
						"responsibility": standard.responsibility,
						"observed_count": 0,
						"unit": standard.unit,
						"result_status": "Recorded",
					},
				)
				existing.add(key)

	def resolve_aggregation_method(self, standard):
		method = standard.aggregation_method or "Worst Case"
		if method != "Worst Case":
			return method
		if standard.comparison_rule in ("At Least", "Isolation Distance"):
			return "Minimum"
		if standard.comparison_rule == "At Most":
			return "Maximum"
		return "All Must Pass"

	def evaluate_take_results(self, standards):
		standards_by_parameter = {row.parameter: row for row in standards}
		takes_by_number = {cint(row.take_number): row for row in self.takes or []}
		valid_take_numbers = set(takes_by_number)
		seen = set()

		for row in self.take_results or []:
			key = (cint(row.take_number), row.parameter)
			if key in seen:
				frappe.throw(
					_("Inspection Take {0} has more than one value for {1}.").format(
						row.take_number, frappe.bold(row.parameter)
					)
				)
			seen.add(key)

			if cint(row.take_number) not in valid_take_numbers:
				frappe.throw(_("Attribute value references missing Inspection Take {0}.").format(row.take_number))

			standard = standards_by_parameter.get(row.parameter)
			if not standard:
				row.result_status = "Not Evaluated"
				row.corrective_action_required = 0
				continue
			if (
				self.sampling_protocol_version == CUMULATIVE_COUNTS_PROTOCOL
				and standard.measurement_scope == "Inspection"
			):
				frappe.throw(
					_("{0} must be recorded once under Inspection-Level Controls.").format(
						frappe.bold(standard.parameter_name)
					)
				)

			row.responsibility = standard.responsibility
			row.unit = standard.unit
			if (
				self.sampling_protocol_version == CUMULATIVE_COUNTS_PROTOCOL
				and standard.calculation_method == "Cumulative Incidence"
			):
				take = takes_by_number[cint(row.take_number)]
				count = row.observed_count
				if count in (None, ""):
					count = row.measured_value
				self.validate_observed_count(count, take.total_plants_counted, standard.parameter_name)
				row.observed_count = cint(count)
				row.measured_value = None
				row.result_status = "Recorded"
				row.corrective_action_required = 0
				continue
			row.result_status = self.evaluate_standard(row, standard)
			row.corrective_action_required = cint(
				row.result_status in FAIL_STATUSES and standard.corrective_action_on_fail
			)

	def evaluate_inspection_observations(self, standards):
		if self.sampling_protocol_version != CUMULATIVE_COUNTS_PROTOCOL:
			return
		standards_by_parameter = {row.parameter: row for row in standards}
		seen = set()
		for row in self.inspection_observations or []:
			if row.parameter in seen:
				frappe.throw(
					_("Inspection-Level Control {0} has been recorded more than once.").format(
						frappe.bold(row.parameter)
					)
				)
			seen.add(row.parameter)
			standard = standards_by_parameter.get(row.parameter)
			if not standard or standard.measurement_scope != "Inspection":
				frappe.throw(_("{0} is not configured as an inspection-level control.").format(row.parameter))
			row.responsibility = standard.responsibility
			row.unit = standard.unit
			row.result_status = self.evaluate_standard(row, standard)
			row.corrective_action_required = cint(
				row.result_status in FAIL_STATUSES and standard.corrective_action_on_fail
			)

	def validate_observed_count(self, count, total_plants, parameter_name):
		if count in (None, "") or flt(count) < 0 or flt(count) != cint(count):
			frappe.throw(_("{0} must be a non-negative whole-number count.").format(parameter_name))
		if cint(total_plants) <= 0:
			frappe.throw(_("Total Plants Counted must be greater than zero."))
		if cint(count) > cint(total_plants):
			frappe.throw(
				_("{0} cannot exceed Total Plants Counted ({1}).").format(
					parameter_name, cint(total_plants)
				)
			)

	def calculate_take_completion(self, standards):
		take_standards = [
			row
			for row in standards
			if self.sampling_protocol_version != CUMULATIVE_COUNTS_PROTOCOL
			or row.measurement_scope != "Inspection"
		]
		mandatory_parameters = {
			row.parameter
			for row in take_standards
			if is_take_value_mandatory(row, self.sampling_protocol_version)
		}
		requires_plant_total = any(
			row.calculation_method == "Cumulative Incidence" for row in take_standards
		)
		results_by_take = defaultdict(dict)
		for row in self.take_results or []:
			results_by_take[cint(row.take_number)][row.parameter] = row

		completed = 0
		for take in self.takes or []:
			results = results_by_take.get(cint(take.take_number), {})
			take.attribute_count = len(results)
			has_location = self.has_valid_coordinates(take)
			has_acceptable_positioning = bool(
				take.positioning_override
				or (
					take.gps_quality_status in ("Good", "Acceptable")
					and take.spacing_status in ("First Take", "Within Standard")
					and take.inside_plot_boundary
				)
			)
			has_mandatory_values = bool(take_standards) and all(
				parameter in results and results[parameter].result_status != "Not Evaluated"
				for parameter in mandatory_parameters
			)
			has_plant_total = not requires_plant_total or cint(take.total_plants_counted) > 0
			take.take_status = (
				"Complete"
				if has_location
				and has_acceptable_positioning
				and has_mandatory_values
				and has_plant_total
				and bool(results)
				else "Incomplete"
			)
			if take.take_status == "Complete":
				completed += 1

		self.completed_take_count = completed
		self.cumulative_total_plants = sum(
			cint(take.total_plants_counted)
			for take in self.takes or []
			if take.take_status == "Complete"
		)

	def calculate_inspection_control_completion(self, standards):
		if self.sampling_protocol_version != CUMULATIVE_COUNTS_PROTOCOL:
			self.controls_completed = 1
			return
		mandatory_controls = {
			row.parameter
			for row in standards
			if row.mandatory and row.measurement_scope == "Inspection"
		}
		recorded = {
			row.parameter
			for row in self.inspection_observations or []
			if row.result_status != "Not Evaluated"
		}
		self.controls_completed = cint(mandatory_controls.issubset(recorded))

	def aggregate_results(self, standards):
		previous = {
			(row.parameter, row.responsibility): {
				"due_date": row.due_date,
				"remarks": row.remarks,
			}
			for row in self.results or []
		}
		results_by_parameter = defaultdict(list)
		for row in self.take_results or []:
			results_by_parameter[row.parameter].append(row)
		observations_by_parameter = {
			row.parameter: [row] for row in self.inspection_observations or []
		}
		takes_by_number = {cint(row.take_number): row for row in self.takes or []}

		self.set("results", [])
		for standard in standards:
			readings = (
				observations_by_parameter.get(standard.parameter, [])
				if (
					self.sampling_protocol_version == CUMULATIVE_COUNTS_PROTOCOL
					and standard.measurement_scope == "Inspection"
				)
				else results_by_parameter.get(standard.parameter, [])
			)
			summary = self.append(
				"results",
				{
					"parameter": standard.parameter,
					"responsibility": standard.responsibility,
					"aggregation_method": standard.aggregation_method,
					"unit": standard.unit,
					"observation_count": len(readings),
				},
			)
			if (
				self.sampling_protocol_version == CUMULATIVE_COUNTS_PROTOCOL
				and standard.calculation_method == "Cumulative Incidence"
			):
				self.populate_cumulative_incidence_result(
					summary, standard, readings, takes_by_number
				)
			else:
				self.populate_aggregate_result(summary, standard, readings)

			old_values = previous.get((summary.parameter, summary.responsibility), {})
			summary.due_date = old_values.get("due_date")
			if old_values.get("remarks"):
				summary.remarks = old_values["remarks"]

	def populate_cumulative_incidence_result(self, summary, standard, readings, takes_by_number):
		observed_count, total_plants, incidence = calculate_cumulative_incidence(
			readings, takes_by_number
		)
		summary.aggregation_method = "Cumulative Incidence"
		summary.cumulative_observed_count = observed_count
		summary.cumulative_total_plants = total_plants
		summary.incidence_percent = round(incidence, 6) if incidence is not None else None
		summary.measured_value = incidence
		summary.unit = "Percent"
		if incidence is None:
			summary.result_status = "Not Evaluated"
			summary.corrective_action_required = 0
			summary.remarks = _("No valid plant-count denominator was captured.")
			return

		summary.result_status = self.evaluate_standard(summary, standard)
		passed = summary.result_status in PASS_STATUSES
		summary.passed_count = cint(passed)
		summary.failed_count = cint(not passed)
		summary.pass_percent = 100 if passed else 0
		summary.corrective_action_required = cint(
			summary.result_status in FAIL_STATUSES and standard.corrective_action_on_fail
		)
		summary.remarks = _(
			"{0} observed across {1} plants; cumulative incidence {2}%."
		).format(observed_count, total_plants, round(incidence, 6))

	def populate_aggregate_result(self, summary, standard, readings):
		if not readings:
			summary.result_status = "Not Evaluated"
			summary.corrective_action_required = 0
			summary.remarks = _("No take values captured.")
			return

		passed = len([row for row in readings if row.result_status in PASS_STATUSES])
		failed = len([row for row in readings if row.result_status in FAIL_STATUSES])
		summary.passed_count = passed
		summary.failed_count = failed
		summary.pass_percent = round((passed / len(readings)) * 100, 2)

		numeric_values = [flt(row.measured_value) for row in readings]
		text_values = [(row.text_value or "").strip() for row in readings if (row.text_value or "").strip()]
		method = standard.aggregation_method

		if standard.data_type in NUMERIC_DATA_TYPES and numeric_values:
			if method == "Minimum":
				summary.measured_value = min(numeric_values)
			elif method == "Maximum":
				summary.measured_value = max(numeric_values)
			elif method == "Sum":
				summary.measured_value = sum(numeric_values)
			else:
				summary.measured_value = sum(numeric_values) / len(numeric_values)

		if text_values:
			unique_values = list(dict.fromkeys(text_values))
			summary.text_value = unique_values[0] if len(unique_values) == 1 else _("Mixed")

		if any(row.result_status == "Auto Reject" for row in readings):
			summary.result_status = "Auto Reject"
		elif method == "All Must Pass":
			if passed == len(readings):
				summary.result_status = "Good" if standard.comparison_rule == "Isolation Distance" else "Pass"
			else:
				summary.result_status = (
					standard.poor_label or "Poor"
					if standard.comparison_rule == "Isolation Distance"
					else "Corrective Action Required"
				)
		else:
			summary.result_status = self.evaluate_standard(summary, standard)

		summary.corrective_action_required = cint(
			summary.result_status in FAIL_STATUSES and standard.corrective_action_on_fail
		)
		summary.remarks = _("{0} of {1} take values passed ({2}%).").format(
			passed, len(readings), summary.pass_percent
		)

	def evaluate_standard(self, row, standard):
		rule = standard.comparison_rule
		measured = row.measured_value
		text = (row.text_value or "").strip().lower()

		if rule == "Isolation Distance":
			passed = measured is not None and flt(measured) >= flt(standard.minimum_value)
			return (standard.good_label or "Good") if passed else (standard.poor_label or "Poor")
		if rule == "At Least":
			passed = measured is not None and flt(measured) >= flt(standard.minimum_value)
		elif rule == "At Most":
			passed = measured is not None and flt(measured) <= flt(standard.maximum_value)
		elif rule == "Between":
			passed = (
				measured is not None
				and flt(standard.minimum_value) <= flt(measured) <= flt(standard.maximum_value)
			)
		elif rule == "Equals":
			passed = text == (standard.expected_text or "").strip().lower()
		elif rule == "Yes Is Pass":
			passed = text in ("yes", "y", "true", "1")
		elif rule == "No Is Pass":
			passed = text in ("no", "n", "false", "0")
		else:
			return row.result_status or "Not Evaluated"

		if passed:
			return "Pass"
		return "Auto Reject" if standard.auto_reject_on_fail else "Corrective Action Required"

	def calculate_compliance(self):
		farmer_rows = []
		supervisor_rows = []
		for row in self.results or []:
			if row.result_status == "Not Evaluated":
				continue
			if row.responsibility in ("Farmer", "Both"):
				farmer_rows.append(row)
			if row.responsibility in ("Outgrower Supervisor", "Both"):
				supervisor_rows.append(row)

		self.farmer_compliance_percent = self._compliance_percent(farmer_rows)
		self.supervisor_compliance_percent = self._compliance_percent(supervisor_rows)
		self.farmer_compliance_status = self._compliance_status(self.farmer_compliance_percent)
		self.supervisor_compliance_status = self._compliance_status(self.supervisor_compliance_percent)

	def _compliance_percent(self, rows):
		if not rows:
			return 0
		passed = len([row for row in rows if row.result_status in PASS_STATUSES])
		return round((passed / len(rows)) * 100, 2)

	def _compliance_status(self, percent):
		if percent < 50:
			return "Non-Compliant"
		if percent <= 80:
			return "Improvements Required"
		return "Compliant"

	def calculate_take_positioning(self):
		settings = get_positioning_settings()
		production_contract = getattr(self, "production_contract", None)
		if production_contract:
			contract_target = flt(
				frappe.db.get_value(
					"Outgrower Production Contract",
					production_contract,
					"target_take_spacing_m",
				)
			)
			if contract_target > 0:
				minimum_tolerance = max(
					flt(settings.target_take_spacing_m) - flt(settings.minimum_take_spacing_m),
					0,
				)
				maximum_tolerance = max(
					flt(settings.maximum_take_spacing_m) - flt(settings.target_take_spacing_m),
					0,
				)
				settings.target_take_spacing_m = contract_target
				settings.minimum_take_spacing_m = max(contract_target - minimum_tolerance, 0)
				settings.maximum_take_spacing_m = contract_target + maximum_tolerance
		points = []
		segments = []
		plot_coordinates = self.get_plot_coordinates()
		distances = []
		accuracies = []
		compliant_spacing_count = 0
		outside_count = 0
		low_accuracy_count = 0
		override_count = 0
		previous = None

		self.target_take_spacing_m = settings.target_take_spacing_m
		self.minimum_take_spacing_standard_m = settings.minimum_take_spacing_m
		self.maximum_take_spacing_standard_m = settings.maximum_take_spacing_m

		for row in sorted(self.takes or [], key=lambda item: item.take_number or item.idx):
			if not self.has_valid_coordinates(row):
				row.gps_quality_status = "Poor"
				row.spacing_status = "First Take" if previous is None else "Too Close"
				low_accuracy_count += 1
				continue
			point = (float(row.latitude), float(row.longitude))
			points.append((cint(row.take_number), *point))
			row.inside_plot_boundary = cint(self.point_inside_polygon(point, plot_coordinates))
			if not row.inside_plot_boundary:
				outside_count += 1

			accuracy = flt(row.gps_accuracy_meters)
			if accuracy > 0:
				accuracies.append(accuracy)
			if accuracy <= 0 or accuracy > settings.maximum_gps_accuracy_m:
				row.gps_quality_status = "Poor"
				low_accuracy_count += 1
			elif accuracy <= settings.preferred_gps_accuracy_m:
				row.gps_quality_status = "Good"
			else:
				row.gps_quality_status = "Acceptable"

			if row.positioning_override:
				override_count += 1

			if previous:
				distance = self.haversine_distance(previous[0], previous[1], point[0], point[1])
				row.distance_from_previous_take_m = round(distance, 2)
				distances.append(distance)
				if distance < settings.minimum_take_spacing_m:
					row.spacing_status = "Too Close"
				elif distance > settings.maximum_take_spacing_m:
					row.spacing_status = "Too Far"
				else:
					row.spacing_status = "Within Standard"
					compliant_spacing_count += 1
				segments.append(
					{
						"from_take_number": previous[2],
						"to_take_number": cint(row.take_number),
						"from": (previous[0], previous[1]),
						"to": point,
						"distance_m": round(distance, 2),
						"spacing_status": row.spacing_status,
					}
				)
			else:
				row.distance_from_previous_take_m = 0
				row.spacing_status = "First Take"
			previous = (*point, cint(row.take_number))

		total_distance = sum(distances)
		self.total_take_path_distance_m = round(total_distance, 2)
		self.average_take_spacing_m = round(statistics.mean(distances), 2) if distances else 0
		self.median_take_spacing_m = round(statistics.median(distances), 2) if distances else 0
		self.minimum_observed_take_spacing_m = round(min(distances), 2) if distances else 0
		self.maximum_observed_take_spacing_m = round(max(distances), 2) if distances else 0
		self.spacing_pair_count = len(distances)
		self.spacing_compliant_count = compliant_spacing_count
		self.spacing_compliance_percent = (
			round((compliant_spacing_count / len(distances)) * 100, 2)
			if distances
			else (100 if points else 0)
		)
		self.average_gps_accuracy_m = round(statistics.mean(accuracies), 2) if accuracies else 0
		self.worst_gps_accuracy_m = round(max(accuracies), 2) if accuracies else 0
		self.low_accuracy_take_count = low_accuracy_count
		self.positioning_override_count = override_count
		self.takes_outside_plot = outside_count
		self.inspection_map_geojson = self.build_map_geojson(points, plot_coordinates, segments)

	def validate_new_take_positioning(self):
		settings = get_positioning_settings()
		for row in self.takes or []:
			if not row.is_new():
				continue
			if not self.has_valid_coordinates(row):
				frappe.throw(
					_("Inspection Take {0} requires valid automatically captured coordinates.").format(
						row.take_number
					)
				)

			distance = (
				flt(row.distance_from_previous_take_m)
				if row.spacing_status != "First Take"
				else None
			)
			issues = get_positioning_issues(
				settings,
				row.gps_accuracy_meters,
				row.location_sample_count,
				0,
				distance,
				row.inside_plot_boundary,
			)
			if not row.captured_at:
				issues.append(_("The device GPS capture timestamp is required."))

			if row.positioning_override:
				if not can_override_positioning(settings):
					frappe.throw(
						_("You are not permitted to override positioning for Inspection Take {0}.").format(
							row.take_number
						)
					)
				if not (row.positioning_override_reason or "").strip():
					frappe.throw(
						_("Inspection Take {0} requires a positioning override reason.").format(
							row.take_number
						)
					)
				row.positioning_override_by = frappe.session.user
			elif issues:
				frappe.throw(
					_("Inspection Take {0} does not meet positioning requirements: {1}").format(
						row.take_number,
						" ".join(issues),
					),
					title=_("Inspection Take Positioning"),
				)

	def has_valid_coordinates(self, take):
		if take.latitude is None or take.longitude is None:
			return False
		latitude = flt(take.latitude)
		longitude = flt(take.longitude)
		return -90 <= latitude <= 90 and -180 <= longitude <= 180 and (latitude != 0 or longitude != 0)

	def calculate_inspection_quality(self):
		settings = get_positioning_settings()
		takes = self.takes or []
		if (
			not takes
			or self.completed_take_count < (self.required_take_count or 1)
			or self.takes_outside_plot
			or self.low_accuracy_take_count
		):
			self.inspection_quality_score = "Poor"
			return

		spacing_is_acceptable = (
			not self.spacing_pair_count
			or self.spacing_compliance_percent >= settings.minimum_spacing_compliance_percent
		)
		if not spacing_is_acceptable:
			self.inspection_quality_score = "Poor"
			return

		all_accuracy_preferred = all(row.gps_quality_status == "Good" for row in takes)
		all_spacing_compliant = not self.spacing_pair_count or self.spacing_compliance_percent == 100
		if all_accuracy_preferred and all_spacing_compliant and not self.positioning_override_count:
			self.inspection_quality_score = "Good"
		else:
			self.inspection_quality_score = "Acceptable"

	def complete_if_all_takes_done(self):
		if self.status == "Cancelled":
			return
		if cint(self.completed_take_count) < (cint(self.required_take_count) or 1):
			return
		if not cint(self.controls_completed):
			return
		self.status = "Awaiting QA Review"
		self.qa_review_status = "Pending"
		if not self.completed_at:
			self.completed_at = now_datetime()

	def calculate_certification_totals(self):
		area = self.plot_area_hectares or 0
		rejected = self.hectares_rejected or 0
		corrective = self.hectares_under_corrective_action or 0
		self.hectares_accepted = max(area - rejected - corrective, 0)

		if any(row.result_status == "Auto Reject" for row in self.results or []):
			self.field_certification_status = "Rejected"
		elif rejected and rejected >= area:
			self.field_certification_status = "Rejected"
		elif rejected:
			self.field_certification_status = "Partially Rejected"
		elif corrective or any(row.corrective_action_required for row in self.results or []):
			self.field_certification_status = "Corrective Action Required"
		elif self.status == "Verified" and self.results:
			self.field_certification_status = "Approved"
		else:
			self.field_certification_status = "Pending"

	def validate_completion(self):
		if self.status not in ("Awaiting QA Review", "Verified"):
			return
		if self.completed_take_count < (self.required_take_count or 1):
			frappe.throw(
				_("Complete all required inspection takes before submitting. Completed {0} of {1}.").format(
					self.completed_take_count, self.required_take_count
				)
			)
		if not cint(self.controls_completed):
			frappe.throw(_("Complete all mandatory inspection-level controls before completion."))
		mandatory_parameters = {row.parameter for row in self.get_standards() if row.mandatory}
		if any(
			row.parameter in mandatory_parameters and row.result_status == "Not Evaluated"
			for row in self.results or []
		):
			frappe.throw(_("All configured inspection attributes must be evaluated before submitting."))
		if not self.completed_at:
			self.completed_at = now_datetime()

	def create_corrective_actions(self):
		for row in self.results or []:
			if not row.corrective_action_required:
				continue
			if frappe.db.exists(
				"Field Corrective Action",
				{"inspection": self.name, "parameter": row.parameter, "status": ["!=", "Closed"]},
			):
				continue
			action = frappe.get_doc(
				{
					"doctype": "Field Corrective Action",
					"source_type": "Inspection",
					"source_name": self.name,
					"source_parameter": row.parameter,
					"inspection": self.name,
					"crop_cycle": self.crop_cycle,
					"plot": self.plot,
					"outgrower": self.outgrower,
					"parameter": row.parameter,
					"responsible_party": row.responsibility,
					"assigned_to": self.get_action_assignee(row.responsibility),
					"verification_assigned_to": self.assigned_to,
					"due_date": row.due_date,
					"status": "Open",
					"description": row.remarks,
				}
			)
			action.insert(ignore_permissions=True)
			action.create_todo()

	def get_action_assignee(self, responsibility):
		if responsibility == "Farmer":
			return None
		if responsibility in ("Outgrower Supervisor", "Both") and self.outgrower:
			return frappe.db.get_value("Outgrower", self.outgrower, "assigned_supervisor")
		return None

	def get_plot_coordinates(self):
		if not self.plot:
			return []
		try:
			plot = frappe.get_doc("Farm Plot", self.plot)
			return [(float(vertex.latitude), float(vertex.longitude)) for vertex in (plot.polygon or [])]
		except Exception:
			return []

	def build_map_geojson(self, points, plot_coordinates, segments=None):
		features = []
		if plot_coordinates:
			coordinates = [[lng, lat] for lat, lng in plot_coordinates]
			coordinates.append(coordinates[0])
			features.append(
				{
					"type": "Feature",
					"properties": {"type": "plot_boundary", "plot": self.plot},
					"geometry": {"type": "Polygon", "coordinates": [coordinates]},
				}
			)
		for segment in segments or []:
			features.append(
				{
					"type": "Feature",
					"properties": {
						"type": "spacing_segment",
						"from_take_number": segment["from_take_number"],
						"to_take_number": segment["to_take_number"],
						"distance_m": segment["distance_m"],
						"spacing_status": segment["spacing_status"],
					},
					"geometry": {
						"type": "LineString",
						"coordinates": [
							[segment["from"][1], segment["from"][0]],
							[segment["to"][1], segment["to"][0]],
						],
					},
				}
			)
		for take_number, lat, lng in points:
			take = next(
				(row for row in self.takes or [] if cint(row.take_number) == take_number),
				None,
			)
			features.append(
				{
					"type": "Feature",
					"properties": {
						"type": "inspection_take",
						"take_number": take_number,
						"gps_accuracy_meters": flt(take.gps_accuracy_meters) if take else 0,
						"gps_quality_status": take.gps_quality_status if take else None,
						"spacing_status": take.spacing_status if take else None,
						"inside_plot_boundary": cint(take.inside_plot_boundary) if take else 0,
						"positioning_override": cint(take.positioning_override) if take else 0,
					},
					"geometry": {"type": "Point", "coordinates": [lng, lat]},
				}
			)
		return json.dumps({"type": "FeatureCollection", "features": features}, indent=2)

	def point_inside_polygon(self, point, polygon):
		if len(polygon) < 3:
			return 1
		x, y = point[1], point[0]
		inside = False
		j = len(polygon) - 1
		for i in range(len(polygon)):
			yi, xi = polygon[i]
			yj, xj = polygon[j]
			intersects = ((yi > y) != (yj > y)) and (
				x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
			)
			if intersects:
				inside = not inside
			j = i
		return cint(inside)

	def haversine_distance(self, lat1, lon1, lat2, lon2):
		radius = 6371000
		lat1_rad = math.radians(lat1)
		lat2_rad = math.radians(lat2)
		dlat = math.radians(lat2 - lat1)
		dlon = math.radians(lon2 - lon1)
		a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
		return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@frappe.whitelist()
def get_take_form_schema(inspection):
	doc = frappe.get_doc("Inspection", inspection)
	doc.check_permission("read")
	doc.populate_context()
	standards = doc.get_standards()
	settings = get_positioning_settings()
	previous_take = next(
		(
			row
			for row in sorted(
				[row for row in doc.takes or [] if doc.has_valid_coordinates(row)],
				key=lambda item: item.take_number or item.idx,
				reverse=True,
			)
		),
		None,
	)
	return {
		"sampling_protocol_version": doc.sampling_protocol_version,
		"required_take_count": doc.required_take_count,
		"completed_take_count": doc.completed_take_count,
		"next_take_number": max([cint(row.take_number) for row in doc.takes or []] or [0]) + 1,
		"previous_take": (
			{
				"take_number": cint(previous_take.take_number),
				"latitude": flt(previous_take.latitude),
				"longitude": flt(previous_take.longitude),
				"gps_accuracy_meters": flt(previous_take.gps_accuracy_meters),
			}
			if previous_take
			else None
		),
		"positioning": {
			"target_take_spacing_m": settings.target_take_spacing_m,
			"minimum_take_spacing_m": settings.minimum_take_spacing_m,
			"maximum_take_spacing_m": settings.maximum_take_spacing_m,
			"preferred_gps_accuracy_m": settings.preferred_gps_accuracy_m,
			"maximum_gps_accuracy_m": settings.maximum_gps_accuracy_m,
			"minimum_location_samples": settings.minimum_location_samples,
			"location_capture_timeout_seconds": settings.location_capture_timeout_seconds,
			"maximum_location_age_seconds": settings.maximum_location_age_seconds,
			"allow_positioning_override": settings.allow_positioning_override,
			"can_override": cint(can_override_positioning(settings)),
		},
		"requires_total_plants": cint(
			any(
				row.calculation_method == "Cumulative Incidence"
				for row in standards
				if row.measurement_scope != "Inspection"
			)
		),
		"attributes": [
			{
				"parameter": row.parameter,
				"label": row.parameter_name,
				"data_type": row.data_type,
				"unit": row.unit,
				"responsibility": row.responsibility,
				"mandatory": cint(
					is_take_value_mandatory(row, doc.sampling_protocol_version)
				),
				"default_value": (
					0
					if is_cumulative_count_standard(row, doc.sampling_protocol_version)
					else None
				),
				"calculation_method": row.calculation_method,
				"description": row.description or row.standard_notes,
			}
			for row in standards
			if (
				doc.sampling_protocol_version != CUMULATIVE_COUNTS_PROTOCOL
				or row.measurement_scope != "Inspection"
			)
		],
	}


@frappe.whitelist()
def add_inspection_take(
	inspection,
	latitude,
	longitude,
	readings,
	total_plants_counted=None,
	gps_accuracy_meters=None,
	captured_at=None,
	location_sample_count=None,
	location_capture_duration_seconds=None,
	location_source=None,
	positioning_override=0,
	positioning_override_reason=None,
	notes=None,
):
	frappe.db.sql("select name from `tabInspection` where name = %s for update", inspection)
	doc = frappe.get_doc("Inspection", inspection)
	doc.check_permission("write")

	if doc.status in ("Awaiting QA Review", "Verified", "Reinspection Required", "Cancelled"):
		frappe.throw(_("Inspection Takes cannot be added to an inspection with status {0}.").format(doc.status))

	doc.populate_context()
	if cint(doc.completed_take_count) >= (cint(doc.required_take_count) or 1):
		frappe.throw(_("All required Inspection Takes have already been completed."))

	latitude = flt(latitude)
	longitude = flt(longitude)
	if not (-90 <= latitude <= 90 and -180 <= longitude <= 180) or (latitude == 0 and longitude == 0):
		frappe.throw(_("A valid automatically captured GPS location is required."))

	if not captured_at:
		frappe.throw(_("The device GPS capture timestamp is required."))
	captured_at = get_datetime(captured_at)
	location_age_seconds = (now_datetime() - captured_at).total_seconds()
	settings = get_positioning_settings()
	previous_take = next(
		(
			row
			for row in sorted(
				[row for row in doc.takes or [] if doc.has_valid_coordinates(row)],
				key=lambda item: item.take_number or item.idx,
				reverse=True,
			)
		),
		None,
	)
	distance_from_previous_take_m = (
		doc.haversine_distance(
			flt(previous_take.latitude),
			flt(previous_take.longitude),
			latitude,
			longitude,
		)
		if previous_take
		else None
	)
	inside_plot_boundary = doc.point_inside_polygon(
		(latitude, longitude),
		doc.get_plot_coordinates(),
	)
	positioning_issues = get_positioning_issues(
		settings,
		gps_accuracy_meters,
		location_sample_count,
		location_age_seconds,
		distance_from_previous_take_m,
		inside_plot_boundary,
	)
	positioning_override = cint(positioning_override)
	if positioning_override:
		if not can_override_positioning(settings):
			frappe.throw(_("You are not permitted to override inspection positioning standards."))
		if not (positioning_override_reason or "").strip():
			frappe.throw(_("An override reason is required for a positioning exception."))
	elif positioning_issues:
		frappe.throw(
			_("Positioning requirements were not met: {0}").format(" ".join(positioning_issues)),
			title=_("Inspection Take Positioning"),
		)

	standards = doc.get_standards()
	if not standards:
		frappe.throw(_("No inspection attributes are configured for this template and production category."))
	take_standards = [
		row
		for row in standards
		if doc.sampling_protocol_version != CUMULATIVE_COUNTS_PROTOCOL
		or row.measurement_scope != "Inspection"
	]
	requires_total_plants = any(
		row.calculation_method == "Cumulative Incidence" for row in take_standards
	)
	if requires_total_plants and cint(total_plants_counted) <= 0:
		frappe.throw(_("Total Plants Counted must be greater than zero."))

	readings = frappe.parse_json(readings) if isinstance(readings, str) else readings
	readings = readings or []
	provided = {row.get("parameter"): row for row in readings if row.get("parameter")}
	if (
		not any(not _reading_is_blank(reading) for reading in provided.values())
		and not any(
			is_cumulative_count_standard(row, doc.sampling_protocol_version)
			for row in take_standards
		)
	):
		frappe.throw(_("Capture at least one inspection attribute value for this Inspection Take."))
	missing = [
		row.parameter_name
		for row in take_standards
		if is_take_value_mandatory(row, doc.sampling_protocol_version)
		and _reading_is_blank(provided.get(row.parameter))
	]
	if missing:
		frappe.throw(_("Enter values for all mandatory attributes: {0}.").format(", ".join(missing)))

	take_number = max([cint(row.take_number) for row in doc.takes or []] or [0]) + 1
	doc.append(
		"takes",
		{
			"take_number": take_number,
			"total_plants_counted": cint(total_plants_counted),
			"latitude": latitude,
			"longitude": longitude,
			"gps_accuracy_meters": flt(gps_accuracy_meters),
			"location_sample_count": cint(location_sample_count),
			"location_capture_duration_seconds": flt(location_capture_duration_seconds),
			"location_source": str(location_source or _("Browser Geolocation"))[:140],
			"captured_at": captured_at,
			"captured_by": frappe.session.user,
			"inside_plot_boundary": inside_plot_boundary,
			"distance_from_previous_take_m": distance_from_previous_take_m,
			"positioning_override": positioning_override,
			"positioning_override_reason": (
				(positioning_override_reason or "").strip() if positioning_override else None
			),
			"positioning_override_by": frappe.session.user if positioning_override else None,
			"notes": notes,
		},
	)

	for standard in take_standards:
		reading = provided.get(standard.parameter)
		if _reading_is_blank(reading):
			continue
		value = reading.get("value")
		is_numeric = standard.data_type in NUMERIC_DATA_TYPES
		is_count = (
			doc.sampling_protocol_version == CUMULATIVE_COUNTS_PROTOCOL
			and standard.calculation_method == "Cumulative Incidence"
		)
		if is_count:
			doc.validate_observed_count(value, total_plants_counted, standard.parameter_name)
		doc.append(
			"take_results",
			{
				"take_number": take_number,
				"parameter": standard.parameter,
				"responsibility": standard.responsibility,
				"observed_count": cint(value) if is_count else None,
				"measured_value": flt(value) if is_numeric and not is_count else None,
				"text_value": None if is_numeric else str(value).strip(),
				"unit": standard.unit,
				"remarks": reading.get("remarks"),
			},
		)

	if doc.status == "Scheduled":
		doc.status = "In Progress"
	if not doc.started_at:
		doc.started_at = now_datetime()
	doc.save()

	return {
		"inspection": doc.name,
		"take_number": take_number,
		"completed_take_count": doc.completed_take_count,
		"required_take_count": doc.required_take_count,
		"status": doc.status,
		"completed_at": doc.completed_at,
		"distance_from_previous_take_m": distance_from_previous_take_m,
		"positioning_issues": positioning_issues,
	}


@frappe.whitelist()
def get_inspection_control_schema(inspection):
	doc = frappe.get_doc("Inspection", inspection)
	doc.check_permission("read")
	doc.populate_context()
	standards = [
		row for row in doc.get_standards() if row.measurement_scope == "Inspection"
	]
	existing = {
		row.parameter: row for row in doc.inspection_observations or []
	}
	return {
		"sampling_protocol_version": doc.sampling_protocol_version,
		"controls_completed": cint(doc.controls_completed),
		"controls": [
			{
				"parameter": row.parameter,
				"label": row.parameter_name,
				"data_type": row.data_type,
				"unit": row.unit,
				"responsibility": row.responsibility,
				"mandatory": cint(row.mandatory),
				"description": row.description or row.standard_notes,
				"value": (
					existing[row.parameter].measured_value
					if row.data_type in NUMERIC_DATA_TYPES and row.parameter in existing
					else existing[row.parameter].text_value
					if row.parameter in existing
					else None
				),
				"remarks": existing[row.parameter].remarks if row.parameter in existing else None,
			}
			for row in standards
		],
	}


@frappe.whitelist()
def save_inspection_controls(inspection, readings):
	frappe.db.sql("select name from `tabInspection` where name = %s for update", inspection)
	doc = frappe.get_doc("Inspection", inspection)
	doc.check_permission("write")
	if doc.status not in ("Scheduled", "In Progress"):
		frappe.throw(_("Inspection controls cannot be changed while status is {0}.").format(doc.status))
	doc.populate_context()
	if doc.sampling_protocol_version != CUMULATIVE_COUNTS_PROTOCOL:
		frappe.throw(_("Inspection-level controls are available only for Cumulative Counts V2 inspections."))

	standards = [
		row for row in doc.get_standards() if row.measurement_scope == "Inspection"
	]
	readings = frappe.parse_json(readings) if isinstance(readings, str) else readings
	provided = {row.get("parameter"): row for row in (readings or []) if row.get("parameter")}
	missing = [
		row.parameter_name
		for row in standards
		if row.mandatory and _reading_is_blank(provided.get(row.parameter))
	]
	if missing:
		frappe.throw(_("Enter all mandatory inspection controls: {0}.").format(", ".join(missing)))

	doc.set("inspection_observations", [])
	for standard in standards:
		reading = provided.get(standard.parameter)
		if _reading_is_blank(reading):
			continue
		value = reading.get("value")
		is_numeric = standard.data_type in NUMERIC_DATA_TYPES
		doc.append(
			"inspection_observations",
			{
				"parameter": standard.parameter,
				"responsibility": standard.responsibility,
				"measured_value": flt(value) if is_numeric else None,
				"text_value": None if is_numeric else str(value).strip(),
				"unit": standard.unit,
				"captured_by": frappe.session.user,
				"captured_at": now_datetime(),
				"remarks": reading.get("remarks"),
			},
		)
	if doc.status == "Scheduled":
		doc.status = "In Progress"
	if not doc.started_at:
		doc.started_at = now_datetime()
	doc.save()
	return {
		"inspection": doc.name,
		"controls_completed": cint(doc.controls_completed),
		"status": doc.status,
		"completed_at": doc.completed_at,
	}


def _require_quality_manager():
	if frappe.session.user != "Administrator" and "Quality Manager" not in frappe.get_roles(
		frappe.session.user
	):
		frappe.throw(
			_("Only a Quality Manager may verify an Inspection or require reinspection."),
			frappe.PermissionError,
		)


@frappe.whitelist()
def review_inspection(inspection, decision, notes=None):
	_require_quality_manager()
	decision = (decision or "").strip()
	if decision not in ("Verified", "Reinspection Required"):
		frappe.throw(_("Select Verified or Reinspection Required."))
	if decision == "Reinspection Required" and not (notes or "").strip():
		frappe.throw(_("QA review notes are required when requesting a reinspection."))

	doc = frappe.get_doc("Inspection", inspection)
	doc.check_permission("read")
	if doc.status != "Awaiting QA Review":
		frappe.throw(
			_("Only Inspections awaiting QA review can be reviewed. Current status: {0}.").format(
				doc.status
			)
		)

	doc.flags.allow_completed_update = True
	doc.status = decision
	doc.qa_review_status = decision
	doc.qa_reviewed_by = frappe.session.user
	doc.qa_reviewed_on = now_datetime()
	doc.qa_review_notes = (notes or "").strip()
	doc.save(ignore_permissions=True)

	reinspection = _create_reinspection(doc, notes) if decision == "Reinspection Required" else None
	return {"inspection": doc.name, "status": doc.status, "reinspection": reinspection}


def _create_reinspection(source, reason):
	reinspection = frappe.get_doc(
		{
			"doctype": "Inspection",
			"inspection_template": source.inspection_template,
			"inspection_type": source.inspection_type,
			"crop_cycle": source.crop_cycle,
			"production_contract": source.production_contract,
			"plot": source.plot,
			"outgrower": source.outgrower,
			"crop": source.crop,
			"season": source.season,
			"production_category": source.production_category,
			"seed_class": source.seed_class,
			"scheduled_date": frappe.utils.today(),
			"assigned_to": source.assigned_to,
			"status": "Scheduled",
			"qa_review_status": "Pending",
			"reinspection_of": source.name,
			"reinspection_reason": (reason or "").strip(),
			"synced": 0,
		}
	)
	reinspection.insert(ignore_permissions=True)
	if source.assigned_to:
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": source.assigned_to,
				"reference_type": "Inspection",
				"reference_name": reinspection.name,
				"description": _("Complete reinspection {0} for {1}.").format(
					reinspection.name, source.plot
				),
				"date": reinspection.scheduled_date,
				"priority": "High",
				"status": "Open",
			}
		).insert(ignore_permissions=True)
	return reinspection.name


def _reading_is_blank(reading):
	if not reading or "value" not in reading:
		return True
	value = reading.get("value")
	return value is None or (isinstance(value, str) and not value.strip())
