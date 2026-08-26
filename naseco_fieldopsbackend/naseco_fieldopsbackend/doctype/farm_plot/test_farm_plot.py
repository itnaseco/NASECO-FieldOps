# Copyright (c) 2026, NASECO and contributors
# See license.txt

import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.farm_plot.farm_plot import (
	FarmPlot,
	_alpha_suffix,
)


class TestFarmPlot(TestCase):
	def test_plot_suffix_sequence_supports_multiple_letters(self):
		self.assertEqual(_alpha_suffix(1), "A")
		self.assertEqual(_alpha_suffix(26), "Z")
		self.assertEqual(_alpha_suffix(27), "AA")

	def test_polygon_area_is_returned_in_hectares(self):
		# A small equatorial polygon close to one hectare.
		area = FarmPlot.calculate_area_hectares(
			None,
			[(0, 0), (0, 0.0009), (0.0009, 0.0009), (0.0009, 0)]
		)
		self.assertAlmostEqual(area, 1, places=1)

	def test_preserves_manual_measurements_when_polygon_exists(self):
		plot = SimpleNamespace(
			polygon=[1, 2, 3],
			flags={},
			area_hectares=2.5,
			perimeter_meters=410,
			centroid_lat=0.34795,
			centroid_lng=32.58295,
			calculate_geospatial_values=Mock(),
			generate_geojson=Mock(),
			clear_geospatial_values=Mock(),
		)
		plot.has_geospatial_values = lambda: FarmPlot.has_geospatial_values(plot)

		FarmPlot.before_save(plot)

		plot.calculate_geospatial_values.assert_not_called()
		plot.generate_geojson.assert_called_once()
		plot.clear_geospatial_values.assert_not_called()

	def test_accepts_valid_manual_plot_measurements(self):
		plot = SimpleNamespace(
			area_hectares=2.5,
			perimeter_meters=410,
			centroid_lat=0.34795,
			centroid_lng=32.58295,
		)

		FarmPlot.validate_geospatial_values(plot)

		self.assertEqual(plot.area_hectares, 2.5)
		self.assertEqual(plot.centroid_lng, 32.58295)

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.farm_plot.farm_plot.frappe.throw",
		side_effect=frappe.ValidationError,
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.farm_plot.farm_plot._",
		side_effect=lambda message: message,
	)
	def test_rejects_incomplete_manual_centroid(self, _translate, _throw):
		plot = SimpleNamespace(
			area_hectares=2.5,
			perimeter_meters=410,
			centroid_lat=0.34795,
			centroid_lng=None,
		)

		with self.assertRaises(frappe.ValidationError):
			FarmPlot.validate_geospatial_values(plot)

	def test_updates_geojson_from_current_polygon(self):
		plot = SimpleNamespace(
			polygon=[
				SimpleNamespace(latitude=0.10, longitude=32.10),
				SimpleNamespace(latitude=0.20, longitude=32.20),
				SimpleNamespace(latitude=0.30, longitude=32.10),
			],
			plot_id="PLOT-001",
			plot_name="North Field",
			area_acres=2.5,
			perimeter_meters=410,
			geojson="stale",
		)

		FarmPlot.generate_geojson(plot)

		geojson = json.loads(plot.geojson)
		coordinates = geojson["geometry"]["coordinates"][0]
		self.assertEqual(coordinates[0], [32.10, 0.10])
		self.assertEqual(coordinates[-1], coordinates[0])

	def test_clears_geojson_when_polygon_is_removed(self):
		plot = SimpleNamespace(
			polygon=[],
			geojson="stale",
			has_geospatial_values=Mock(return_value=True),
			clear_geospatial_values=Mock(),
		)

		FarmPlot.before_save(plot)

		self.assertIsNone(plot.geojson)
		plot.clear_geospatial_values.assert_not_called()

	def test_normalizes_manually_entered_polygon_order(self):
		plot = SimpleNamespace(
			polygon=[
				SimpleNamespace(latitude=0.20, longitude=32.20, order_index=2, idx=1),
				SimpleNamespace(latitude=0.10, longitude=32.10, order_index=1, idx=2),
				SimpleNamespace(latitude=0.30, longitude=32.10, order_index=3, idx=3),
			]
		)

		FarmPlot.validate_and_normalize_polygon(plot)

		self.assertEqual(
			[(row.latitude, row.longitude, row.order_index) for row in plot.polygon],
			[
				(0.10, 32.10, 1),
				(0.20, 32.20, 2),
				(0.30, 32.10, 3),
			],
		)

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.farm_plot.farm_plot.frappe.throw",
		side_effect=frappe.ValidationError,
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.farm_plot.farm_plot._",
		side_effect=lambda message: message,
	)
	def test_rejects_invalid_manual_coordinate(self, _translate, _throw):
		plot = SimpleNamespace(
			polygon=[
				SimpleNamespace(latitude=91, longitude=32.10, order_index=1, idx=1),
				SimpleNamespace(latitude=0.20, longitude=32.20, order_index=2, idx=2),
				SimpleNamespace(latitude=0.30, longitude=32.10, order_index=3, idx=3),
			]
		)

		with self.assertRaises(frappe.ValidationError):
			FarmPlot.validate_and_normalize_polygon(plot)
