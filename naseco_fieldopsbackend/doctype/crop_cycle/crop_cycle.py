# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class CropCycle(Document):
	def before_save(self):
		"""Auto-update status based on dates"""
		self.update_status()

	def update_status(self):
		"""
		Update crop cycle status based on dates:
		- PLANNED: start_date is in the future
		- ACTIVE: started but not harvested
		- COMPLETED: actual_harvest_date is set
		"""
		if self.actual_harvest_date:
			self.status = "COMPLETED"
		elif self.start_date:
			current_date = getdate(now_datetime())
			start_date = getdate(self.start_date)

			if start_date > current_date:
				self.status = "PLANNED"
			else:
				self.status = "ACTIVE"
		else:
			self.status = "PLANNED"
