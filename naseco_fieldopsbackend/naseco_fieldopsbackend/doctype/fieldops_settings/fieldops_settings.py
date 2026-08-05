# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class FieldOpsSettings(Document):
	def validate(self):
		target = flt(self.target_take_spacing_m)
		minimum = flt(self.minimum_take_spacing_m)
		maximum = flt(self.maximum_take_spacing_m)
		preferred_accuracy = flt(self.preferred_gps_accuracy_m)
		maximum_accuracy = flt(self.maximum_gps_accuracy_m)

		if target <= 0 or minimum <= 0 or maximum <= 0:
			frappe.throw(_("Take spacing values must be greater than zero."))
		if not minimum <= target <= maximum:
			frappe.throw(_("Target take spacing must be between the minimum and maximum spacing."))
		if preferred_accuracy <= 0 or maximum_accuracy <= 0:
			frappe.throw(_("GPS accuracy values must be greater than zero."))
		if preferred_accuracy > maximum_accuracy:
			frappe.throw(_("Preferred GPS accuracy cannot exceed maximum GPS accuracy."))
		if cint(self.minimum_location_samples) < 1:
			frappe.throw(_("Minimum location samples must be at least one."))
		if cint(self.location_capture_timeout_seconds) < 5:
			frappe.throw(_("Location capture timeout must be at least five seconds."))
		if cint(self.maximum_location_age_seconds) < 5:
			frappe.throw(_("Maximum location age must be at least five seconds."))
		if not 0 <= flt(self.minimum_spacing_compliance_percent) <= 100:
			frappe.throw(_("Minimum spacing compliance must be between 0 and 100 percent."))
		if self.allow_positioning_override and not self.positioning_override_role:
			frappe.throw(_("Select the role permitted to override positioning standards."))

