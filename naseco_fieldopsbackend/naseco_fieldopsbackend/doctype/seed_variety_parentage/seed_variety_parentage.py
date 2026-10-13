# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class SeedVarietyParentage(Document):
	def validate(self):
		self.crop = frappe.db.get_value("Crop Variety", self.output_variety, "crop")
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))
		seen_roles = set()
		seen_parents = set()
		for row in self.parents or []:
			if row.parent_variety == self.output_variety:
				frappe.throw(_("The output variety cannot be its own parent."))
			if frappe.db.get_value("Crop Variety", row.parent_variety, "crop") != self.crop:
				frappe.throw(_("Parent variety {0} must belong to crop {1}.").format(row.parent_variety, self.crop))
			if row.parent_role in seen_roles:
				frappe.throw(_("Parent role {0} is duplicated.").format(row.parent_role))
			if row.parent_variety in seen_parents:
				frappe.throw(_("Parent variety {0} is duplicated.").format(row.parent_variety))
			seen_roles.add(row.parent_role)
			seen_parents.add(row.parent_variety)
		if {"Female", "Male"} - seen_roles:
			frappe.throw(_("Parentage must define exactly one Female and one Male parent."))

	def before_submit(self):
		overlap = frappe.db.sql(
			"""select name from `tabSeed Variety Parentage`
			where output_variety=%s and docstatus=1 and status='Active' and name!=%s
			  and (effective_to is null or effective_to >= %s)
			  and (%s is null or effective_from <= %s) limit 1""",
			(self.output_variety, self.name, self.effective_from, self.effective_to, self.effective_to),
		)
		if overlap:
			frappe.throw(_("An overlapping active parentage already exists for {0}.").format(self.output_variety))
		self.status = "Active"

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
