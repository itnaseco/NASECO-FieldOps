import frappe
from frappe.model.document import Document

class FieldTrip(Document):
	def validate(self):
		self.field_officer = self.field_officer or frappe.session.user
		if self.status == "In Progress":
			other = frappe.db.exists("Field Trip", {"field_officer": self.field_officer, "status": "In Progress", "name": ["!=", self.name or ""]})
			if other: frappe.throw("Complete the active Field Trip before starting another.")
		if self.status == "Completed":
			if not self.end_datetime or not self.trip_summary: frappe.throw("End time and trip summary are required.")
			if frappe.db.exists("Field Visit", {"field_trip": self.name, "status": "in_progress"}): frappe.throw("Complete the active visit before completing this trip.")
		if self.opening_odometer is not None and self.closing_odometer is not None:
			if self.closing_odometer < self.opening_odometer: frappe.throw("Closing odometer cannot be below opening odometer.")
			self.calculated_distance_km = self.closing_odometer - self.opening_odometer
