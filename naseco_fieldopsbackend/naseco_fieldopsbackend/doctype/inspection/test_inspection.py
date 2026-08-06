# Copyright (c) 2026, NASECO and Contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection import (
	CUMULATIVE_COUNTS_PROTOCOL,
	Inspection,
	_reading_is_blank,
	calculate_cumulative_incidence,
	get_positioning_issues,
	is_take_value_mandatory,
)


class TestInspection(TestCase):
	def test_compliance_boundaries(self):
		self.assertEqual(Inspection._compliance_status(None, 49.99), "Non-Compliant")
		self.assertEqual(Inspection._compliance_status(None, 50), "Improvements Required")
		self.assertEqual(Inspection._compliance_status(None, 80), "Improvements Required")
		self.assertEqual(Inspection._compliance_status(None, 80.01), "Compliant")

	def test_zero_is_a_valid_take_value(self):
		self.assertFalse(_reading_is_blank({"value": 0}))
		self.assertTrue(_reading_is_blank({"value": ""}))
		self.assertTrue(_reading_is_blank(None))

	def test_cumulative_incidence_uses_combined_counts_and_denominator(self):
		readings = [
			SimpleNamespace(take_number=1, observed_count=1, measured_value=1),
			SimpleNamespace(take_number=2, observed_count=9, measured_value=9),
		]
		takes = {
			1: SimpleNamespace(total_plants_counted=100),
			2: SimpleNamespace(total_plants_counted=900),
		}

		observed, total_plants, incidence = calculate_cumulative_incidence(readings, takes)

		self.assertEqual(observed, 10)
		self.assertEqual(total_plants, 1000)
		self.assertEqual(incidence, 1)

	def test_cumulative_count_take_values_are_optional(self):
		standard = SimpleNamespace(
			mandatory=1,
			calculation_method="Cumulative Incidence",
		)
		self.assertFalse(is_take_value_mandatory(standard, CUMULATIVE_COUNTS_PROTOCOL))
		self.assertTrue(is_take_value_mandatory(standard, "Legacy Percentage V1"))

	def test_missing_cumulative_counts_are_recorded_as_zero(self):
		inspection = SimpleNamespace(
			sampling_protocol_version=CUMULATIVE_COUNTS_PROTOCOL,
			takes=[SimpleNamespace(take_number=1, total_plants_counted=100)],
			take_results=[],
		)

		def append(fieldname, values):
			self.assertEqual(fieldname, "take_results")
			row = SimpleNamespace(**values)
			inspection.take_results.append(row)
			return row

		inspection.append = append
		standards = [
			SimpleNamespace(
				parameter="Offtypes in females",
				responsibility="Farmer",
				measurement_scope="Inspection Take",
				calculation_method="Cumulative Incidence",
				unit="Nos",
			)
		]

		Inspection.ensure_cumulative_count_results(inspection, standards)

		self.assertEqual(len(inspection.take_results), 1)
		self.assertEqual(inspection.take_results[0].observed_count, 0)
		self.assertEqual(inspection.take_results[0].unit, "Nos")

	def test_mandatory_inspection_controls_are_recorded_once(self):
		standards = [
			SimpleNamespace(parameter="Isolation distance", mandatory=1, measurement_scope="Inspection"),
			SimpleNamespace(parameter="Time isolation", mandatory=1, measurement_scope="Inspection"),
		]
		inspection = SimpleNamespace(
			sampling_protocol_version=CUMULATIVE_COUNTS_PROTOCOL,
			inspection_observations=[
				SimpleNamespace(parameter="Isolation distance", result_status="Good")
			],
			controls_completed=0,
		)

		Inspection.calculate_inspection_control_completion(inspection, standards)
		self.assertEqual(inspection.controls_completed, 0)

		inspection.inspection_observations.append(
			SimpleNamespace(parameter="Time isolation", result_status="Pass")
		)
		Inspection.calculate_inspection_control_completion(inspection, standards)
		self.assertEqual(inspection.controls_completed, 1)

	def test_isolation_controls_use_adequate_or_inadequate(self):
		standard = self._standard(
			comparison_rule="Equals",
			expected_text="Adequate",
		)
		self.assertEqual(
			Inspection.evaluate_standard(None, SimpleNamespace(measured_value=None, text_value="Adequate"), standard),
			"Pass",
		)
		self.assertEqual(
			Inspection.evaluate_standard(None, SimpleNamespace(measured_value=None, text_value="Inadequate"), standard),
			"Corrective Action Required",
		)

	def test_failed_auto_reject_standard_is_auto_rejected(self):
		standard = self._standard(
			comparison_rule="At Most",
			maximum_value=0.1,
			auto_reject_on_fail=1,
		)
		result = Inspection.evaluate_standard(
			None,
			SimpleNamespace(measured_value=0.11, text_value=""),
			standard,
		)
		self.assertEqual(result, "Auto Reject")

	def test_worst_case_aggregation_uses_rule_direction(self):
		at_least = self._standard(comparison_rule="At Least", aggregation_method="Worst Case")
		at_most = self._standard(comparison_rule="At Most", aggregation_method="Worst Case")
		yes_no = self._standard(comparison_rule="Yes Is Pass", aggregation_method="Worst Case")
		self.assertEqual(Inspection.resolve_aggregation_method(None, at_least), "Minimum")
		self.assertEqual(Inspection.resolve_aggregation_method(None, at_most), "Maximum")
		self.assertEqual(Inspection.resolve_aggregation_method(None, yes_no), "All Must Pass")

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection._",
		side_effect=lambda message: message,
	)
	def test_positioning_issues_enforce_accuracy_samples_spacing_and_boundary(self, _translate):
		settings = self._positioning_settings()
		self.assertEqual(
			get_positioning_issues(settings, 2.5, 3, 10, 5.0, True),
			[],
		)

		issues = get_positioning_issues(settings, 8, 1, 90, 1.5, False)
		self.assertEqual(len(issues), 5)
		self.assertTrue(any("GPS accuracy" in issue for issue in issues))
		self.assertTrue(any("stable GPS" in issue for issue in issues))
		self.assertTrue(any("capture window" in issue for issue in issues))
		self.assertTrue(any("move at least" in issue for issue in issues))
		self.assertTrue(any("outside" in issue for issue in issues))

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection.get_positioning_settings"
	)
	def test_take_positioning_grades_each_five_meter_segment(self, get_settings):
		get_settings.return_value = self._positioning_settings()
		takes = [
			SimpleNamespace(
				take_number=1,
				latitude=0.34765000,
				longitude=32.58265000,
				gps_accuracy_meters=2.1,
				positioning_override=0,
			),
			SimpleNamespace(
				take_number=2,
				latitude=0.34765000,
				longitude=32.58269500,
				gps_accuracy_meters=2.4,
				positioning_override=0,
			),
		]
		inspection = SimpleNamespace(
			takes=takes,
			get_plot_coordinates=lambda: [],
			has_valid_coordinates=lambda take: Inspection.has_valid_coordinates(None, take),
			point_inside_polygon=lambda point, polygon: 1,
			haversine_distance=lambda lat1, lon1, lat2, lon2: Inspection.haversine_distance(
				None, lat1, lon1, lat2, lon2
			),
			build_map_geojson=lambda points, polygon, segments: "{}",
		)

		Inspection.calculate_take_positioning(inspection)

		self.assertEqual(takes[0].spacing_status, "First Take")
		self.assertEqual(takes[1].spacing_status, "Within Standard")
		self.assertAlmostEqual(takes[1].distance_from_previous_take_m, 5.0, delta=0.1)
		self.assertEqual(inspection.spacing_compliance_percent, 100)
		self.assertEqual(inspection.low_accuracy_take_count, 0)

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection.now_datetime",
		return_value="2026-07-25 16:00:00",
	)
	def test_final_required_take_completes_inspection(self, _now_datetime):
		inspection = SimpleNamespace(
			status="In Progress",
			completed_take_count=4,
			required_take_count=4,
			controls_completed=1,
			completed_at=None,
		)
		Inspection.complete_if_all_takes_done(inspection)
		self.assertEqual(inspection.status, "Awaiting QA Review")
		self.assertEqual(inspection.qa_review_status, "Pending")
		self.assertEqual(inspection.completed_at, "2026-07-25 16:00:00")

	def test_incomplete_inspection_remains_in_progress(self):
		inspection = SimpleNamespace(
			status="In Progress",
			completed_take_count=3,
			required_take_count=4,
			controls_completed=1,
			completed_at=None,
		)
		Inspection.complete_if_all_takes_done(inspection)
		self.assertEqual(inspection.status, "In Progress")
		self.assertIsNone(inspection.completed_at)

	def test_completed_takes_wait_for_mandatory_inspection_controls(self):
		inspection = SimpleNamespace(
			status="In Progress",
			completed_take_count=4,
			required_take_count=4,
			controls_completed=0,
			completed_at=None,
		)

		Inspection.complete_if_all_takes_done(inspection)

		self.assertEqual(inspection.status, "In Progress")
		self.assertIsNone(inspection.completed_at)

	def _standard(self, **values):
		defaults = {
			"comparison_rule": "At Most",
			"aggregation_method": "Worst Case",
			"minimum_value": None,
			"maximum_value": None,
			"expected_text": None,
			"good_label": "Good",
			"poor_label": "Poor",
			"auto_reject_on_fail": 0,
		}
		defaults.update(values)
		return SimpleNamespace(**defaults)

	def _positioning_settings(self):
		return SimpleNamespace(
			target_take_spacing_m=5,
			minimum_take_spacing_m=3,
			maximum_take_spacing_m=7,
			minimum_spacing_compliance_percent=80,
			preferred_gps_accuracy_m=3,
			maximum_gps_accuracy_m=5,
			minimum_location_samples=3,
			location_capture_timeout_seconds=30,
			maximum_location_age_seconds=60,
			allow_positioning_override=1,
			positioning_override_role="System Manager",
		)
