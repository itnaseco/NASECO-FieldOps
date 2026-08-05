# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from naseco_fieldopsbackend.crop_cycle_lifecycle import STAGE_NAMES, canonical_stage_name


class AgronomyActivityTemplate(Document):
	def validate(self):
		self.stage_name = canonical_stage_name(self.stage_name)
		if self.stage_name not in STAGE_NAMES:
			frappe.throw(_("Select an approved crop-cycle stage."))
		if self.day_offset_end in (None, ""):
			self.day_offset_end = self.day_offset_from_planting
		if self.day_offset_end < self.day_offset_from_planting:
			frappe.throw(_("Activity End Day cannot be before its Start Day."))
