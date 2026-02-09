# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import base64
import json
import math
import re
import time

import frappe
from frappe.model.document import Document
from frappe.utils.file_manager import save_file


class FarmPlot(Document):
	def before_save(self):
		"""Calculate area, perimeter, and centroid from polygon vertices"""
		if self.polygon and len(self.polygon) >= 3:
			self.calculate_geospatial_values()
			self.generate_geojson()

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

	def calculate_geospatial_values(self):
		"""Calculate area (acres), perimeter (meters), and centroid from GPS vertices"""
		vertices = [(float(v.latitude), float(v.longitude)) for v in self.polygon]

		# Calculate area using spherical polygon formula
		self.area_acres = self.calculate_area_acres(vertices)

		# Calculate perimeter using Haversine distance
		self.perimeter_meters = self.calculate_perimeter_meters(vertices)

		# Calculate centroid using unit vector averaging
		centroid = self.calculate_centroid(vertices)
		self.centroid_lat = centroid[0]
		self.centroid_lng = centroid[1]

	def calculate_area_acres(self, vertices):
		"""
		Calculate area of spherical polygon using spherical excess formula.
		Returns area in acres.
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

		# Convert square meters to acres (1 acre = 4046.86 sq meters)
		acres = area_sq_meters / 4046.86

		return round(acres, 2)

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
		"""Generate GeoJSON representation of the polygon"""
		if not self.polygon:
			return

		coordinates = [[float(v.longitude), float(v.latitude)] for v in self.polygon]
		# Close the polygon by adding the first point at the end
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
				"area_acres": self.area_acres or 0,
				"perimeter_meters": self.perimeter_meters or 0
			}
		}

		self.geojson = json.dumps(geojson, indent=2)
