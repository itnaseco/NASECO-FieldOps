# Copyright (c) 2026, Naseco and Contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season import (
	Season,
	get_season_status,
)


class TestSeason(TestCase):
	def test_date_derived_status_uses_inclusive_boundaries(self):
		self.assertEqual(get_season_status("2026-07-15", "2027-01-31", "2026-07-14"), "Not Started")
		self.assertEqual(get_season_status("2026-07-15", "2027-01-31", "2026-07-15"), "Ongoing")
		self.assertEqual(get_season_status("2026-07-15", "2027-01-31", "2027-01-31"), "Ongoing")
		self.assertEqual(get_season_status("2026-07-15", "2027-01-31", "2027-02-01"), "Ended")

	def test_rejects_end_date_before_start_date(self):
		season = SimpleNamespace(start_date="2026-08-01", end_date="2026-07-31")
		fake_frappe = SimpleNamespace(throw=Mock(side_effect=frappe.ValidationError))

		with (
			patch(
				"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season.frappe",
				fake_frappe,
			),
			patch(
				"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season._",
				side_effect=lambda message: message,
			),
			self.assertRaises(frappe.ValidationError),
		):
			Season.validate_date_range(season)

	def test_rejects_overlapping_season(self):
		season = SimpleNamespace(
			name="New Season",
			start_date="2026-07-15",
			end_date="2027-01-31",
		)
		fake_frappe = SimpleNamespace(
			bold=lambda value: value,
			db=SimpleNamespace(get_value=Mock(return_value="Existing Season")),
			throw=Mock(side_effect=frappe.ValidationError),
		)

		with (
			patch(
				"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season.frappe",
				fake_frappe,
			),
			patch(
				"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season._",
				side_effect=lambda message: message,
			),
			self.assertRaises(frappe.ValidationError),
		):
			Season.validate_no_overlap(season)
