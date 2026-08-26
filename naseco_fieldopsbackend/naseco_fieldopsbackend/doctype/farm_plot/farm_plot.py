# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import base64
import json
import math
import re
import time

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils.file_manager import save_file


class FarmPlot(Document):
	def autoname(self):
		if self.plot_id:
			self.name = self.plot_id
			return

		auto_generate = frappe.db.get_single_value(
			"FieldOps Settings", "auto_generate_plot_ids"
		)
		if auto_generate in (None, ""):
			auto_generate = 1
		if not auto_generate:
			frappe.throw(_("Plot ID is required when automatic plot naming is disabled."))
		if not self.outgrower:
			frappe.throw(_("Outgrower is required before a Farm Plot ID can be generated."))

		self.plot_id = get_next_plot_id(self.outgrower)
		self.name = self.plot_id

	def validate(self):
		self.validate_and_normalize_polygon()
		self.validate_geospatial_values()

	def before_save(self):
		"""Calculate missing measurements while preserving values entered in Desk."""
		if self.polygon and len(self.polygon) >= 3:
			if self.flags.get("force_geospatial_calculation") or not self.has_geospatial_values():
				self.calculate_geospatial_values()
			self.generate_geojson()
		else:
			if not self.has_geospatial_values():
				self.clear_geospatial_values()
			self.geojson = None

	def after_insert(self):
		self._ensure_map_image_from_base64()

	def on_update(self):
		self._ensure_map_image_from_base64()

	def _ensure_map_image_from_base64(self):
		if not self.map_image_base64 or self.map_image:
			return

		b64 = (self.map_image_base64 or "").strip()
		if not b64:
			return

		mime = None
		data = b64
		match = re.match(r"^data:(image/[^;]+);base64,(.*)$", b64, flags=re.IGNORECASE | re.DOTALL)
		if match:
			mime = match.group(1).lower()
			data = match.group(2)

		try:
			content = base64.b64decode(data)
		except Exception:
			frappe.log_error("Invalid base64 map image for Farm Plot")
			return

		ext_map = {
			"image/png": ".png",
			"image/jpeg": ".jpg",
			"image/jpg": ".jpg",
			"image/webp": ".webp",
			"image/gif": ".gif",
		}
		ext = ext_map.get(mime, ".png")
		filename = f"plot_{self.plot_id or self.name or 'map'}_{int(time.time())}{ext}"

		try:
			file_doc = save_file(filename, content, self.doctype, self.name, is_private=0)
			if file_doc and file_doc.file_url:
				frappe.db.set_value(self.doctype, self.name, "map_image", file_doc.file_url, update_modified=False)
		except Exception:
			frappe.log_error("Failed to save map image file from base64")

	def validate_and_normalize_polygon(self):
		if not self.polygon:
			return

		ordered_vertices = sorted(
			self.polygon,
			key=lambda row: (row.order_index or row.idx or 0, row.idx or 0),
		)
		self.polygon = ordered_vertices

		unique_coordinates = set()
		first_coordinate = None
		for index, vertex in enumerate(self.polygon, start=1):
			if vertex.latitude in (None, ""):
				frappe.throw(_("Latitude is required in coordinate row {0}.").format(index))
			if vertex.longitude in (None, ""):
				frappe.throw(_("Longitude is required in coordinate row {0}.").format(index))

			latitude = flt(vertex.latitude)
			longitude = flt(vertex.longitude)

			if not -90 <= latitude <= 90:
				frappe.throw(
					_("Latitude in coordinate row {0} must be between -90 and 90.").format(index)
				)
			if not -180 <= longitude <= 180:
				frappe.throw(
					_("Longitude in coordinate row {0} must be between -180 and 180.").format(index)
				)

			coordinate = (round(latitude, 8), round(longitude, 8))
			is_closing_coordinate = (
				index == len(self.polygon)
				and len(self.polygon) > 3
				and coordinate == first_coordinate
			)
			if coordinate in unique_coordinates and not is_closing_coordinate:
				frappe.throw(
					_("Coordinate row {0} duplicates another polygon vertex.").format(index)
				)

			first_coordinate = first_coordinate or coordinate
			unique_coordinates.add(coordinate)
			vertex.latitude = latitude
			vertex.longitude = longitude
			vertex.order_index = index
			vertex.idx = index

		if len(unique_coordinates) < 3:
			frappe.throw(_("A plot polygon requires at least three unique coordinates."))

	def validate_geospatial_values(self):
		area_hectares = getattr(self, "area_hectares", None)
		legacy_area = getattr(self, "area_acres", None)
		if area_hectares in (None, "") and legacy_area not in (None, ""):
			area_hectares = flt(legacy_area) * 0.40468564224
			self.area_hectares = area_hectares
		if area_hectares not in (None, "") and flt(area_hectares) < 0:
			frappe.throw(_("Area cannot be negative."))
		if area_hectares not in (None, ""):
			self.area_acres = round(flt(area_hectares) * 2.47105381467, 4)
		if self.perimeter_meters not in (None, "") and flt(self.perimeter_meters) < 0:
			frappe.throw(_("Perimeter cannot be negative."))

		has_latitude = self.centroid_lat not in (None, "")
		has_longitude = self.centroid_lng not in (None, "")
		if has_latitude != has_longitude:
			frappe.throw(
				_("Both Centroid Latitude and Centroid Longitude are required when either is entered.")
			)
		if has_latitude and not -90 <= flt(self.centroid_lat) <= 90:
			frappe.throw(_("Centroid Latitude must be between -90 and 90."))
		if has_longitude and not -180 <= flt(self.centroid_lng) <= 180:
			frappe.throw(_("Centroid Longitude must be between -180 and 180."))

	def has_geospatial_values(self):
		return any(
			value not in (None, "")
			for value in (
				getattr(self, "area_hectares", None) or getattr(self, "area_acres", None),
				self.perimeter_meters,
				self.centroid_lat,
				self.centroid_lng,
			)
		)

	def clear_geospatial_values(self):
		self.area_hectares = 0
		self.area_acres = 0
		self.perimeter_meters = 0
		self.centroid_lat = None
		self.centroid_lng = None
		self.geojson = None

	def calculate_geospatial_values(self):
		"""Calculate area (hectares), perimeter (meters), and centroid from GPS vertices."""
		vertices = [(float(v.latitude), float(v.longitude)) for v in self.polygon]

		# Calculate area using spherical polygon formula
		self.area_hectares = self.calculate_area_hectares(vertices)
		self.area_acres = round(self.area_hectares * 2.47105381467, 4)

		# Calculate perimeter using Haversine distance
		self.perimeter_meters = self.calculate_perimeter_meters(vertices)

		# Calculate centroid using unit vector averaging
		centroid = self.calculate_centroid(vertices)
		self.centroid_lat = centroid[0]
		self.centroid_lng = centroid[1]

	def calculate_area_hectares(self, vertices):
		"""Calculate spherical polygon area in hectares.
		"""
		if len(vertices) < 3:
			return 0.0

		# Earth's radius in meters
		R = 6371000

		# Convert to radians
		vertices_rad = [(math.radians(lat), math.radians(lon)) for lat, lon in vertices]

		# Calculate area using spherical excess
		area_sq_meters = 0.0
		n = len(vertices_rad)

		for i in range(n):
			lat1, lon1 = vertices_rad[i]
			lat2, lon2 = vertices_rad[(i + 1) % n]

			# Spherical excess formula component
			area_sq_meters += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))

		area_sq_meters = abs(area_sq_meters * R * R / 2.0)

		return round(area_sq_meters / 10000, 4)

	def calculate_area_acres(self, vertices):
		"""Compatibility helper for legacy clients."""
		return round(self.calculate_area_hectares(vertices) * 2.47105381467, 4)

	def calculate_perimeter_meters(self, vertices):
		"""
		Calculate perimeter using Haversine distance formula.
		Returns perimeter in meters.
		"""
		if len(vertices) < 2:
			return 0.0

		perimeter = 0.0
		n = len(vertices)

		for i in range(n):
			lat1, lon1 = vertices[i]
			lat2, lon2 = vertices[(i + 1) % n]

			# Haversine distance
			distance = self.haversine_distance(lat1, lon1, lat2, lon2)
			perimeter += distance

		return round(perimeter, 2)

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

	def calculate_centroid(self, vertices):
		"""
		Calculate centroid of polygon using unit vector averaging.
		Returns (latitude, longitude) tuple.
		"""
		if not vertices:
			return (0.0, 0.0)

		# Convert to Cartesian coordinates
		x = y = z = 0.0

		for lat, lon in vertices:
			lat_rad = math.radians(lat)
			lon_rad = math.radians(lon)

			x += math.cos(lat_rad) * math.cos(lon_rad)
			y += math.cos(lat_rad) * math.sin(lon_rad)
			z += math.sin(lat_rad)

		n = len(vertices)
		x /= n
		y /= n
		z /= n

		# Convert back to latitude/longitude
		lon_centroid = math.atan2(y, x)
		hyp = math.sqrt(x * x + y * y)
		lat_centroid = math.atan2(z, hyp)

		return (round(math.degrees(lat_centroid), 6), round(math.degrees(lon_centroid), 6))

	def generate_geojson(self):
		"""Update GeoJSON from the current polygon."""
		if not self.polygon:
			self.geojson = None
			return

		coordinates = [[float(v.longitude), float(v.latitude)] for v in self.polygon]
		if coordinates[-1] != coordinates[0]:
			coordinates.append(coordinates[0])

		geojson = {
			"type": "Feature",
			"geometry": {
				"type": "Polygon",
				"coordinates": [coordinates]
			},
			"properties": {
				"plot_id": self.plot_id,
				"plot_name": self.plot_name or "",
				"area_hectares": getattr(self, "area_hectares", None)
				or flt(getattr(self, "area_acres", 0)) * 0.40468564224,
				"perimeter_meters": self.perimeter_meters or 0
			}
		}

		self.geojson = json.dumps(geojson, indent=2)


@frappe.whitelist()
def recalculate_plot_measurements(farm_plot):
	doc = frappe.get_doc("Farm Plot", farm_plot)
	doc.check_permission("write")
	if len(doc.polygon or []) < 3:
		frappe.throw(_("At least three polygon coordinates are required to calculate plot measurements."))

	doc.validate_and_normalize_polygon()
	doc.flags.force_geospatial_calculation = True
	doc.save()
	return {
		"area_hectares": doc.area_hectares,
		"perimeter_meters": doc.perimeter_meters,
		"centroid_lat": doc.centroid_lat,
		"centroid_lng": doc.centroid_lng,
	}


def get_next_plot_id(outgrower):
	"""Allocate the next alphabetic plot suffix under an outgrower."""
	prefix = str(outgrower).strip()
	limit = int(
		frappe.db.get_single_value("FieldOps Settings", "plot_alpha_suffix_limit") or 2
	)
	limit = min(max(limit, 1), 4)

	# Lock this outgrower's existing rows for the duration of the insert transaction.
	existing = frappe.db.sql(
		"""
		select plot_id
		from `tabFarm Plot`
		where outgrower = %s
		for update
		""",
		outgrower,
		as_dict=True,
	)
	used = {row.plot_id for row in existing if row.plot_id}
	for index in range(1, sum(26**width for width in range(1, limit + 1)) + 1):
		candidate = f"{prefix}-{_alpha_suffix(index)}"
		if candidate not in used and not frappe.db.exists("Farm Plot", candidate):
			return candidate

	frappe.throw(
		_("No Farm Plot suffixes remain for Outgrower {0}.").format(frappe.bold(outgrower))
	)


def _alpha_suffix(index):
	letters = []
	while index:
		index, remainder = divmod(index - 1, 26)
		letters.append(chr(65 + remainder))
	return "".join(reversed(letters))
