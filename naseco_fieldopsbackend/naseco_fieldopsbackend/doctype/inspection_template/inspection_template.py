# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate


class InspectionTemplate(Document):
    def before_validate(self):
        if not frappe.db.exists("Inspection Template", self.name or ""):
            self.lifecycle_status = "Draft"
            self.active = 0

    def validate(self):
        previous = self.get_doc_before_save()
        if previous and previous.get("lifecycle_status") in ("Published", "Retired"):
            frappe.throw(_("Published and retired templates are immutable. Create a new version to edit this configuration."))
        if self.get("effective_from") and self.get("effective_to") and getdate(self.effective_to) < getdate(self.effective_from):
            frappe.throw(_("Effective To cannot precede Effective From."))
        if self.get("stage_definition") and not frappe.db.exists("Stage Definition", self.stage_definition):
            frappe.throw(_("Select a valid Recipe Stage Definition."))
        keys = set()
        for row in self.get("quality_parameters") or []:
            if not cint(row.get("active")):
                continue
            key = (row.parameter, row.get("production_category"), row.get("seed_class"))
            if key in keys:
                frappe.throw(_("Parameter {0} has duplicate applicability rows.").format(row.parameter))
            keys.add(key)
            if row.comparison_rule == "Between" and (row.minimum_value is None or row.maximum_value is None):
                frappe.throw(_("Between requires both bounds for parameter {0}.").format(row.parameter))
            if row.minimum_value is not None and row.maximum_value is not None and flt(row.minimum_value) > flt(row.maximum_value):
                frappe.throw(_("Minimum exceeds maximum for parameter {0}.").format(row.parameter))
        for row in self.get("applicability_rules") or []:
            if row.effective_from and row.effective_to and getdate(row.effective_to) < getdate(row.effective_from):
                frappe.throw(_("Applicability row {0} has an invalid date window.").format(row.idx))
