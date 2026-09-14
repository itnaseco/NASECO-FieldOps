# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import math


class FieldVisit(Document):
	def validate(self):
		self.visited_by = self.visited_by or frappe.session.user
		if self.crop_cycle and frappe.db.get_value("Crop Cycle", self.crop_cycle, "plot") != self.plot:
			frappe.throw("The visit crop cycle does not belong to the selected plot.")
		if self.field_trip:
			trip = frappe.get_doc("Field Trip", self.field_trip)
			if trip.field_officer != self.visited_by or trip.status != "In Progress":
				frappe.throw("The visit must belong to the officer's active Field Trip.")
		if self.status == "in_progress":
			other = frappe.db.exists("Field Visit", {"visited_by": self.visited_by, "status": "in_progress", "name": ["!=", self.name or ""]})
			if other:
				frappe.throw("Complete the active Field Visit before starting another.")
		if self.status == "completed" and not self.actual_end:
			frappe.throw("An actual end time is required to complete a visit.")
		"""Validate GPS distance from plot centroid"""
		if self.plot and self.gps_lat and self.gps_lng:
			self.calculate_distance_from_plot()
			self.validate_gps_proximity()

	def calculate_distance_from_plot(self):
		"""Calculate distance from visit GPS to plot centroid"""
		plot = frappe.get_doc("Farm Plot", self.plot)

		if plot.centroid_lat and plot.centroid_lng:
			distance = self.haversine_distance(
				self.gps_lat, self.gps_lng,
				plot.centroid_lat, plot.centroid_lng
			)
			# Convert meters to kilometers
			self.distance_from_plot = round(distance / 1000, 2)

	def validate_gps_proximity(self):
		"""Warn if visit is too far from plot"""
		if self.distance_from_plot and self.distance_from_plot > 5:
			frappe.msgprint(
				f"Warning: Visit location is {self.distance_from_plot} km from plot centroid. "
				"Please verify the GPS coordinates.",
				indicator="orange",
				title="GPS Distance Warning"
			)

	def haversine_distance(self, lat1, lon1, lat2, lon2):
		"""
		Calculate distance between two GPS points using Haversine formula.
		Returns distance in meters.
		"""
		R = 6371000  # Earth's radius in meters

		lat1_rad = math.radians(lat1)
		lat2_rad = math.radians(lat2)
		dlat = math.radians(lat2 - lat1)
		dlon = math.radians(lon2 - lon1)

		a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
		c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

		distance = R * c
		return distance
