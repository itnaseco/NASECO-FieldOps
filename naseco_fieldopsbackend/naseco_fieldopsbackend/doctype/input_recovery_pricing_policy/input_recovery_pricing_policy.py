import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime


class InputRecoveryPricingPolicy(Document):
	def validate(self):
		if flt(self.default_markup_percent) < 0:
			frappe.throw(_("Default Markup % cannot be negative."))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))
		seen = set()
		for row in self.exceptions or []:
			key = (row.item_code or "", row.item_group or "", row.crop or "", row.variety or "")
			if key in seen:
				frappe.throw(_("Duplicate recovery-pricing exception in row {0}.").format(row.idx))
			seen.add(key)
			if flt(row.markup_percent) < 0:
				frappe.throw(_("Markup % cannot be negative in row {0}.").format(row.idx))

	def before_submit(self):
		self.status = "Active"
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
		if frappe.db.exists(
			self.doctype,
			{
				"company": self.company,
				"status": "Active",
				"docstatus": 1,
				"name": ["!=", self.name],
			},
		):
			frappe.throw(_("Another active Input Recovery Pricing Policy exists for this company."))

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
