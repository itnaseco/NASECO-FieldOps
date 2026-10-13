# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime


class ParentSeedLotAnalysis(Document):
	def validate(self):
		if not 0 < flt(self.germination_percent) <= 100:
			frappe.throw(_("Germination percentage must be greater than zero and at most 100."))
		if flt(self.thousand_kernel_weight_g) <= 0:
			frappe.throw(_("Thousand-kernel weight must be greater than zero."))
		if self.valid_until and getdate(self.valid_until) < getdate(self.test_date):
			frappe.throw(_("Valid Until cannot be before Test Date."))
		batch_item = frappe.db.get_value("Batch", self.batch_no, "item")
		if batch_item != self.item_code:
			frappe.throw(_("Batch {0} does not belong to Item {1}.").format(self.batch_no, self.item_code))
		mapping = frappe.db.exists(
			"Crop Variety Seed Item",
			{
				"parent": self.parent_variety,
				"parenttype": "Crop Variety",
				"item_code": self.item_code,
				"seed_category": self.seed_category,
				"seed_class": self.seed_class,
				"item_purpose": "Parent Seed",
			},
		)
		if not mapping:
			frappe.throw(_("Item {0} is not mapped to parent variety {1} with the selected category and class.").format(self.item_code, self.parent_variety))

	def before_submit(self):
		self.status = "Approved"
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
