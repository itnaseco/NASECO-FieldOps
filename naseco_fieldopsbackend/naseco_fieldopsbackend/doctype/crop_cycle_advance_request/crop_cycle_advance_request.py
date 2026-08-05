# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from naseco_fieldopsbackend.fieldops_finance import (
	calculate_crop_cycle_exposure,
	create_payment_entry_from_advance_request,
	get_crop_cycle_context,
)


class CropCycleAdvanceRequest(Document):
	def before_validate(self):
		self.set_context()
		self.set_exposure()

	def validate(self):
		self.validate_amounts()

	def before_submit(self):
		self.validate_purchase_order()
		self.status = "Approved"

	def on_submit(self):
		create_payment_entry_from_advance_request(self)

	def before_cancel(self):
		self.validate_payment_can_cancel()

	def on_cancel(self):
		if self.payment_entry and frappe.db.get_value(
			"Payment Entry", self.payment_entry, "docstatus"
		) == 0:
			frappe.delete_doc(
				"Payment Entry",
				self.payment_entry,
				ignore_permissions=True,
			)
		self.db_set("status", "Cancelled", update_modified=False)

	def set_context(self):
		if not self.crop_cycle:
			return
		context = get_crop_cycle_context(self.crop_cycle)
		self.production_contract = context.cycle.production_contract
		self.company = context.company
		self.outgrower = context.outgrower.name
		self.supplier = context.supplier
		self.purchase_order = self.purchase_order or context.cycle.purchase_order
		self.requested_by = self.requested_by or frappe.session.user
		self.request_date = self.request_date or nowdate()
		self.currency = frappe.db.get_value("Company", self.company, "default_currency")

	def set_exposure(self):
		if not self.crop_cycle:
			return
		exposure = calculate_crop_cycle_exposure(self.crop_cycle)
		self.expected_harvest_value = exposure.expected_harvest_value
		self.risk_adjusted_harvest_value = exposure.risk_adjusted_harvest_value
		self.recoverable_stock_value = exposure.recoverable_stock_value
		self.cash_advanced = exposure.cash_advanced
		self.pending_cash_advance = exposure.pending_cash_advance
		self.exposure_limit = exposure.exposure_limit
		self.available_advance_capacity = exposure.available_advance_capacity

	def validate_amounts(self):
		if flt(self.requested_amount) <= 0:
			frappe.throw(_("Requested Amount must be greater than zero."))
		if flt(self.approved_amount) < 0 or flt(self.approved_amount) > flt(self.requested_amount):
			frappe.throw(_("Approved Amount must be between zero and the Requested Amount."))
		if self.docstatus == 0 and flt(self.approved_amount) > flt(self.available_advance_capacity):
			frappe.throw(
				_("Approved Amount exceeds the available crop-cycle advance capacity of {0}.").format(
					frappe.format_value(
						self.available_advance_capacity,
						{"fieldtype": "Currency", "options": self.currency},
					)
				),
				title=_("Exposure Limit Exceeded"),
			)

	def validate_purchase_order(self):
		if not self.supplier:
			frappe.throw(_("Create or link the Outgrower Supplier before approving an advance."))
		settings = frappe.get_single("FieldOps Settings")
		if not settings.require_purchase_order_for_advance:
			return
		if not self.purchase_order:
			frappe.throw(_("A Harvest Purchase Order is required before approving this advance."))
		if frappe.db.get_value("Purchase Order", self.purchase_order, "docstatus") != 1:
			frappe.throw(
				_("Purchase Order {0} must be submitted before approving this advance.").format(
					frappe.bold(self.purchase_order)
				)
			)

	def validate_payment_can_cancel(self):
		if not self.payment_entry or not frappe.db.exists("Payment Entry", self.payment_entry):
			return
		if frappe.db.get_value("Payment Entry", self.payment_entry, "docstatus") == 1:
			frappe.throw(
				_("Cancel Payment Entry {0} before cancelling this advance request.").format(
					frappe.bold(self.payment_entry)
				)
			)


@frappe.whitelist()
def create_payment_entry(advance_request):
	doc = frappe.get_doc("Crop Cycle Advance Request", advance_request)
	if doc.docstatus != 1:
		frappe.throw(_("Submit the advance request before creating a Payment Entry."))
	return create_payment_entry_from_advance_request(doc)


@frappe.whitelist()
def refresh_exposure(advance_request):
	doc = frappe.get_doc("Crop Cycle Advance Request", advance_request)
	doc.set_exposure()
	doc.db_set(
		{
			"expected_harvest_value": doc.expected_harvest_value,
			"risk_adjusted_harvest_value": doc.risk_adjusted_harvest_value,
			"recoverable_stock_value": doc.recoverable_stock_value,
			"cash_advanced": doc.cash_advanced,
			"pending_cash_advance": doc.pending_cash_advance,
			"exposure_limit": doc.exposure_limit,
			"available_advance_capacity": doc.available_advance_capacity,
		},
		update_modified=False,
	)
	return doc.as_dict()
