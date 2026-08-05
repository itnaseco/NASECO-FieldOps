# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from naseco_fieldopsbackend.crop_cycle_lifecycle import STAGE_NAMES, canonical_stage_name


class AgronomyReportTemplate(Document):
	def validate(self):
		self.stage_name = canonical_stage_name(self.stage_name)
		if self.stage_name not in STAGE_NAMES:
			frappe.throw(_("Select one of the nine approved crop-cycle stages."))
		if self.window_end_day < self.window_start_day:
			frappe.throw(_("Window End Day cannot be before Window Start Day."))
		if cint(self.template_version) <= 0:
			frappe.throw(_("Template Version must be greater than zero."))
		if not 0 <= flt(self.overall_pass_threshold_percent) <= 100:
			frappe.throw(_("Overall Pass Threshold must be between 0 and 100."))

		seen = set()
		for row in self.parameters or []:
			row.parameter_code = (row.parameter_code or "").strip().upper().replace(" ", "_")
			if not row.parameter_code:
				frappe.throw(_("Parameter Code is required in row {0}.").format(row.idx))
			if row.parameter_code in seen:
				frappe.throw(_("Parameter Code {0} is duplicated.").format(row.parameter_code))
			seen.add(row.parameter_code)
			self.validate_parameter_standard(row)

		self.increment_version_for_standard_changes()

	def validate_parameter_standard(self, row):
		if row.evaluation_mode != "Rule Based":
			return
		if not row.comparison_rule:
			frappe.throw(_("Comparison Rule is required for {0}.").format(row.parameter_label))
		if flt(row.weight) <= 0:
			frappe.throw(_("Evaluation Weight must be greater than zero for {0}.").format(row.parameter_label))

		rule = row.comparison_rule
		if rule in ("At Least", "Between") and row.minimum_value in (None, ""):
			frappe.throw(_("Minimum Passing Value is required for {0}.").format(row.parameter_label))
		if rule in ("At Most", "Between") and row.maximum_value in (None, ""):
			frappe.throw(_("Maximum Passing Value is required for {0}.").format(row.parameter_label))
		if rule == "Between" and flt(row.minimum_value) > flt(row.maximum_value):
			frappe.throw(_("Minimum Passing Value cannot exceed Maximum Passing Value for {0}.").format(row.parameter_label))
		if rule in ("Equals", "Expected Value") and not (row.expected_value or "").strip():
			frappe.throw(_("Expected Passing Value is required for {0}.").format(row.parameter_label))
		if rule in ("At Least", "At Most", "Between") and row.data_type not in (
			"Number", "Count", "Percent"
		):
			frappe.throw(_("{0} requires a numeric data type.").format(rule))
		if rule == "Within Report Window" and row.data_type != "Date":
			frappe.throw(_("Within Report Window requires a Date parameter."))
		if cint(row.corrective_action_due_days) < 0:
			frappe.throw(_("Corrective Action Due Days cannot be negative."))

	def increment_version_for_standard_changes(self):
		previous = self.get_doc_before_save()
		if not previous or previous.is_new():
			return
		if self.standard_signature() == self.standard_signature(previous):
			return
		self.template_version = max(cint(self.template_version), cint(previous.template_version) + 1)

	def standard_signature(self, document=None):
		document = document or self
		fields = (
			"parameter_code", "data_type", "unit", "mandatory", "evaluation_mode",
			"comparison_rule", "minimum_value", "maximum_value", "expected_value",
			"severity", "weight", "allow_not_applicable", "corrective_action_on_fail",
			"failure_action", "corrective_action_due_days",
		)
		return (
			flt(document.overall_pass_threshold_percent),
			cint(document.critical_failure_override),
			tuple(tuple(row.get(fieldname) for fieldname in fields) for row in document.parameters or []),
		)
