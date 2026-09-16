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


@frappe.whitelist()
def get_visit_work_summary(visit):
	"""Return field work explicitly linked to a Field Visit.

	Mobile records can temporarily retain the visit's offline correlation ID
	until Frappe naming is reconciled.  Query all authoritative identifiers for
	the visit instead of silently hiding otherwise valid linked work.
	"""
	if not visit or not frappe.db.exists("Field Visit", visit):
		frappe.throw("Field Visit not found.", frappe.DoesNotExistError)
	visit_doc = frappe.get_doc("Field Visit", visit)
	if not frappe.has_permission("Field Visit", "read", doc=visit_doc):
		frappe.throw(
			"You are not permitted to view this Field Visit.",
			frappe.PermissionError,
		)
	visit_identifiers = list(
		dict.fromkeys(
			value
			for value in (
				visit_doc.name,
				visit_doc.get("visit_id"),
				visit_doc.get("external_id"),
			)
			if value
		)
	)

	definitions = (
		{
			"key": "activities",
			"doctype": "Stage Activity",
			"link_field": "visit",
			"title_fields": ("title", "activity_name", "activity_template"),
			"date_fields": ("activity_date", "completed_on", "due_date"),
		},
		{
			"key": "reports",
			"doctype": "Agronomy Report",
			"link_field": "field_visit",
			"title_fields": ("report_number", "stage_name", "report_template"),
			"date_fields": ("report_date", "location_captured_at"),
		},
		{
			"key": "inspections",
			"doctype": "Inspection",
			"link_field": "field_visit",
			"title_fields": ("inspection_type", "inspection_template"),
			"date_fields": ("completed_at", "started_at", "scheduled_date"),
		},
	)
	result = {"visit": visit_doc.name, "total": 0}
	for definition in definitions:
		meta = frappe.get_meta(definition["doctype"])
		if not meta.has_field(definition["link_field"]):
			result[definition["key"]] = []
			continue
		fields = ["name"]
		for fieldname in (
			"status",
			*definition["title_fields"],
			*definition["date_fields"],
		):
			if meta.has_field(fieldname) and fieldname not in fields:
				fields.append(fieldname)
		rows = frappe.get_list(
			definition["doctype"],
			filters={definition["link_field"]: ["in", visit_identifiers]},
			fields=fields,
			order_by="modified desc",
		)
		result[definition["key"]] = [
			{
				"name": row.name,
				"title": next(
					(
						row.get(fieldname)
						for fieldname in definition["title_fields"]
						if row.get(fieldname)
					),
					row.name,
				),
				"status": row.get("status") or "",
				"date": next(
					(
						row.get(fieldname)
						for fieldname in definition["date_fields"]
						if row.get(fieldname)
					),
					None,
				),
			}
			for row in rows
		]
		result["total"] += len(rows)
	return result
