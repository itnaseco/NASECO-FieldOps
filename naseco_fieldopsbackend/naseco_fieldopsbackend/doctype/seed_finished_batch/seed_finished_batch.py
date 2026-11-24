import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class SeedFinishedBatch(Document):
	"""Links one finished ERPNext Batch to exactly one physical harvest lot."""

	def before_validate(self):
		if not self.processing_handoff:
			return
		handoff = frappe.db.get_value(
			"Seed Processing Handoff", self.processing_handoff,
			["harvest_lot", "dispatch_date"], as_dict=True,
		)
		if not handoff:
			frappe.throw(_("Seed Processing Handoff {0} does not exist.").format(self.processing_handoff))
		if self.harvest_lot and self.harvest_lot != handoff.harvest_lot:
			frappe.throw(_("Harvest Lot must match the Processing Handoff."))
		self.harvest_lot = handoff.harvest_lot
		if self.received_date and getdate(self.received_date) < getdate(handoff.dispatch_date):
			frappe.throw(_("Received Date cannot be before Dispatch Date."))

	def validate(self):
		if not self.is_new():
			previous = self.get_doc_before_save()
			for field in ("processing_handoff", "harvest_lot", "item_code", "batch_no"):
				if previous and previous.get(field) != self.get(field):
					frappe.throw(_("{0} cannot change after the finished Batch is saved.").format(field))
		if flt(self.received_qty_kg) <= 0:
			frappe.throw(_("Received Quantity (kg) must be greater than zero."))
		if not self.is_new():
			previous = self.get_doc_before_save()
			if previous and flt(previous.received_qty_kg) != flt(self.received_qty_kg):
				if frappe.db.exists("Parent Seed Lot Analysis", {"batch_no": self.batch_no}):
					frappe.throw(_("Received Quantity cannot change after a lot analysis exists for this Batch."))
		batch_item = frappe.db.get_value("Batch", self.batch_no, "item")
		if batch_item != self.item_code:
			frappe.throw(_("Batch {0} does not belong to Item {1}.").format(self.batch_no, self.item_code))
		if not self.stock_voucher_type or not self.stock_voucher:
			frappe.throw(_("Select the submitted ERPNext stock voucher for this finished Batch."))
		if self.stock_voucher_type not in ("Purchase Receipt", "Stock Entry", "Stock Reconciliation"):
			frappe.throw(_("Select a supported Stock Voucher Type."))
		if self.stock_voucher:
			voucher = frappe.get_doc(self.stock_voucher_type, self.stock_voucher)
			if voucher.docstatus != 1:
				frappe.throw(_("Stock Voucher must be submitted."))
			if not any(row.item_code == self.item_code for row in voucher.get("items", [])):
				frappe.throw(_("Stock Voucher must contain Item {0}.").format(self.item_code))
			batches = [
				row.batch_no for row in voucher.get("items", [])
				if row.item_code == self.item_code and row.get("batch_no")
			]
			if batches and self.batch_no not in batches:
				frappe.throw(_("Stock Voucher Item batch does not match Batch {0}.").format(self.batch_no))

	def on_trash(self):
		if frappe.db.exists("Parent Seed Lot Analysis", {"batch_no": self.batch_no}):
			frappe.throw(_("A Parent Seed Lot Analysis exists for Batch {0}.").format(self.batch_no))
