# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime
from datetime import datetime


class Outgrower(Document):
	def before_save(self):
		"""Auto-calculate years since registration and farmer status"""
		if self.registration_date:
			self.calculate_years_since_registration()
			self.update_farmer_status()

	def calculate_years_since_registration(self):
		"""Calculate years since registration date"""
		registration_date = getdate(self.registration_date)
		current_date = getdate(now_datetime())

		# Calculate the difference in years
		years = (current_date - registration_date).days / 365.25

		self.years_since_registration = round(years, 1)

	def update_farmer_status(self):
		"""Update farmer status based on years since registration"""
		years = self.years_since_registration or 0

		if years < 1:
			self.farmer_status = "Beginner"
		elif years < 2:
			self.farmer_status = "Intermediate"
		elif years < 5:
			self.farmer_status = "Experienced"
		else:
			self.farmer_status = "Expert"
