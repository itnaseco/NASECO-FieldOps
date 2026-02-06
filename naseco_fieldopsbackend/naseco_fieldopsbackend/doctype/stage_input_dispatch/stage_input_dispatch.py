# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StageInputDispatch(Document):
	def before_insert(self):
		"""Auto-populate fields from input request"""
		if self.input_request:
			request = frappe.get_doc("Stage Input Request", self.input_request)
			self.crop_cycle = request.crop_cycle
			self.stage = request.stage
			self.input_name = request.input_name

	def after_insert(self):
		"""Update parent request fulfillment status"""
		self.update_request_status()

	def on_update(self):
		"""Update parent request fulfillment status"""
		self.update_request_status()

	def on_trash(self):
		"""Update parent request when dispatch is deleted"""
		self.update_request_status()

	def update_request_status(self):
		"""Trigger recalculation of parent request fulfillment status"""
		if self.input_request:
			request = frappe.get_doc("Stage Input Request", self.input_request)
			request.update_fulfillment_status()
