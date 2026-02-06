# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StageInputRequest(Document):
	def after_insert(self):
		"""Initialize fulfillment tracking"""
		self.quantity_dispatched = 0
		self.quantity_remaining = self.quantity_needed

	def on_update(self):
		"""Recalculate fulfillment status when updated"""
		self.update_fulfillment_status()

	def update_fulfillment_status(self):
		"""
		Calculate quantity dispatched from all related dispatches
		and update status accordingly
		"""
		# Get all dispatches for this request
		dispatches = frappe.get_all(
			"Stage Input Dispatch",
			filters={"input_request": self.name},
			fields=["quantity_dispatched"]
		)

		# Sum up dispatched quantities
		total_dispatched = sum([d.quantity_dispatched for d in dispatches])
		self.quantity_dispatched = total_dispatched
		self.quantity_remaining = self.quantity_needed - total_dispatched

		# Update status based on fulfillment
		if self.quantity_remaining <= 0:
			self.status = "Fulfilled"
		elif self.quantity_dispatched > 0:
			self.status = "Partially Fulfilled"
		elif self.status == "Pending":
			# Keep pending status if nothing dispatched
			pass

		# Save without triggering recursion
		self.db_update()
		frappe.db.commit()
