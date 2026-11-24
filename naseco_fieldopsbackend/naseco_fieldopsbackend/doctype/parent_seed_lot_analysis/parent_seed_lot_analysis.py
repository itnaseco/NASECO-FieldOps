# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime


class ParentSeedLotAnalysis(Document):
	def before_validate(self):
		if self.is_new() and self.batch_no and not self.finished_batch:
			self.finished_batch = frappe.db.get_value(
				"Seed Finished Batch", {"batch_no": self.batch_no}, "name"
			)

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
		if self.finished_batch:
			finished = frappe.db.get_value(
				"Seed Finished Batch", self.finished_batch,
				["batch_no", "item_code", "harvest_lot"], as_dict=True,
			)
			if not finished or finished.batch_no != self.batch_no or finished.item_code != self.item_code:
				frappe.throw(_("Finished Batch Provenance must match this Item and Batch."))
			source = frappe.db.get_value(
				"Seed Field Harvest Lot", finished.harvest_lot,
				["variety", "season", "production_category"], as_dict=True,
			)
			if source.variety != self.parent_variety:
				frappe.throw(_("Parent Variety must match the finished Batch harvest source."))
			if source.production_category and source.production_category != self.seed_category:
				frappe.throw(_("Seed Category must match the finished Batch harvest source."))
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
