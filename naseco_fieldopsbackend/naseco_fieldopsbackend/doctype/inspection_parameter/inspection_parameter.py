# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class InspectionParameter(Document):
	def validate(self):
		if self.data_type == "Select" and not self.get_select_options():
			frappe.throw(_("Select Options are required for a Select inspection parameter."))

	def get_select_options(self):
		return [row.strip() for row in (self.select_options or "").splitlines() if row.strip()]
