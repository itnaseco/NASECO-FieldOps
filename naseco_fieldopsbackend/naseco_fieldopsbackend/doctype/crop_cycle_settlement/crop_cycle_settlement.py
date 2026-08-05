# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from naseco_fieldopsbackend.fieldops_finance import (
	create_purchase_invoice_from_settlement,
	get_crop_cycle_context,
	populate_settlement_sources,
)


class CropCycleSettlement(Document):
	def before_validate(self):
		self.set_context()
		if self.docstatus == 0 and self.crop_cycle:
			populate_settlement_sources(self)
		self.calculate_totals()

	def validate(self):
		if not self.harvest_receipts:
			frappe.throw(
				_("At least one submitted harvest Purchase Receipt is required.")
			)
		self.validate_assessment_coverage()
		if flt(self.invoice_total) < 0:
			frappe.throw(_("Settlement deductions cannot make the invoice total negative."))
		for row in self.adjustments:
			if flt(row.amount) <= 0:
				frappe.throw(_("Adjustment amount must be greater than zero in row {0}.").format(row.idx))
			if not row.account:
				frappe.throw(_("An account is required for adjustment row {0}.").format(row.idx))

	def on_submit(self):
		create_purchase_invoice_from_settlement(self)

	def before_cancel(self):
		if self.purchase_invoice and frappe.db.get_value(
			"Purchase Invoice", self.purchase_invoice, "docstatus"
		) == 1:
			frappe.throw(
				_("Cancel Purchase Invoice {0} before cancelling this settlement.").format(
					frappe.bold(self.purchase_invoice)
				)
			)

	def on_cancel(self):
		if self.purchase_invoice and frappe.db.get_value(
			"Purchase Invoice", self.purchase_invoice, "docstatus"
		) == 0:
			frappe.delete_doc(
				"Purchase Invoice",
				self.purchase_invoice,
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
		self.purchase_order = context.cycle.purchase_order
		self.posting_date = self.posting_date or nowdate()
		self.currency = context.cycle.currency or frappe.db.get_value(
			"Company", context.company, "default_currency"
		)

	def calculate_totals(self):
		self.receipt_book_value = sum(
			flt(row.amount) for row in self.harvest_receipts
		)
		self.quality_deductions = sum(
			flt(row.screen_deduction) + flt(row.reject_deduction)
			for row in self.pricing_lines
		)
		self.potential_deferred_bonus = sum(
			flt(row.potential_bonus_amount) for row in self.pricing_lines
		)
		self.gross_harvest_value = (
			sum(flt(row.initial_payable_value) for row in self.pricing_lines)
			if self.pricing_lines
			else self.receipt_book_value
		)
		self.stock_recovery_due = sum(
			flt(row.recoverable_amount) for row in self.stock_inputs
		)
		self.cash_advance_available = sum(
			flt(row.available_amount) for row in self.cash_advances
		)
		self.other_additions = sum(
			flt(row.amount) for row in self.adjustments if row.add_or_deduct == "Add"
		)
		self.other_deductions = sum(
			flt(row.amount) for row in self.adjustments if row.add_or_deduct == "Deduct"
		)

		available_for_recovery = max(
			flt(self.gross_harvest_value) + flt(self.other_additions) - flt(self.other_deductions),
			0,
		)
		self.stock_recovery_to_deduct = min(
			flt(self.stock_recovery_due),
			available_for_recovery,
		)
		self.stock_recovery_shortfall = max(
			flt(self.stock_recovery_due) - flt(self.stock_recovery_to_deduct),
			0,
		)
		self.invoice_total = max(
			available_for_recovery - flt(self.stock_recovery_to_deduct),
			0,
		)
		self.cash_advance_to_allocate = min(
			flt(self.cash_advance_available),
			flt(self.invoice_total),
		)
		self.cash_advance_shortfall = max(
			flt(self.cash_advance_available) - flt(self.cash_advance_to_allocate),
			0,
		)
		self.net_payable = max(
			flt(self.invoice_total) - flt(self.cash_advance_to_allocate),
			0,
		)
		self.unrecovered_balance = (
			flt(self.stock_recovery_shortfall) + flt(self.cash_advance_shortfall)
		)
		self.status = "Prepared" if self.harvest_receipts else "Draft"

	def validate_assessment_coverage(self):
		if not self.pricing_policy:
			return
		assessed_items = set(
			frappe.get_all(
				"Seed Harvest Quality Assessment",
				filters={"crop_cycle": self.crop_cycle, "docstatus": 1},
				pluck="purchase_receipt_item",
			)
		)
		missing = [
			row.purchase_receipt_item
			for row in self.harvest_receipts
			if row.purchase_receipt_item not in assessed_items
		]
		if missing:
			frappe.throw(
				_(
					"Every harvest receipt row must have a submitted Seed Harvest Quality "
					"Assessment before settlement. Missing rows: {0}"
				).format(", ".join(missing))
			)
		if not self.pricing_lines:
			frappe.throw(
				_("No submitted seed-harvest assessment produced a contract pricing line.")
			)


@frappe.whitelist()
def refresh_settlement(settlement):
	doc = frappe.get_doc("Crop Cycle Settlement", settlement)
	if doc.docstatus != 0:
		frappe.throw(_("Only a draft settlement can be refreshed."))
	populate_settlement_sources(doc)
	doc.calculate_totals()
	doc.save()
	return doc


@frappe.whitelist()
def create_purchase_invoice(settlement):
	doc = frappe.get_doc("Crop Cycle Settlement", settlement)
	if doc.docstatus != 1:
		frappe.throw(_("Submit the settlement before creating its Purchase Invoice."))
	return create_purchase_invoice_from_settlement(doc)


@frappe.whitelist()
def create_net_payment(settlement):
	doc = frappe.get_doc("Crop Cycle Settlement", settlement)
	if not doc.purchase_invoice:
		frappe.throw(_("No Purchase Invoice is linked to this settlement."))
	if frappe.db.get_value("Purchase Invoice", doc.purchase_invoice, "docstatus") != 1:
		frappe.throw(_("Submit the Purchase Invoice before creating the net payment."))

	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	payment = get_payment_entry("Purchase Invoice", doc.purchase_invoice)
	if flt(payment.paid_amount) <= 0:
		frappe.throw(_("The Purchase Invoice has no outstanding amount to pay."))
	if payment.meta.has_field("crop_cycle"):
		payment.crop_cycle = doc.crop_cycle
	payment.custom_outgrower = doc.outgrower
	payment.custom_crop_cycle_settlement = doc.name
	payment.custom_production_contract = doc.production_contract
	payment.insert(ignore_permissions=True)
	return payment.name
