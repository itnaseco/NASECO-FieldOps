from unittest import TestCase
from types import SimpleNamespace

from naseco_fieldopsbackend import api


class TestMobileSecurity(TestCase):
	def test_dispatch_recorded_during_visit_can_sync_after_completion(self):
		visit = SimpleNamespace(
			actual_start="2026-09-17 08:00:00",
			actual_end="2026-09-17 10:00:00",
		)
		self.assertTrue(
			api._evidence_within_completed_visit(
				"Stage Input Dispatch",
				{"dispatch_date": "2026-09-17"},
				visit,
			)
		)
		self.assertFalse(
			api._evidence_within_completed_visit(
				"Stage Input Dispatch",
				{"dispatch_date": "2026-09-18"},
				visit,
			)
		)

	def test_only_known_store_or_doctype_names_are_resolved(self):
		self.assertEqual(api._resolve_doctype("plots", strict=True), "Farm Plot")
		self.assertEqual(api._resolve_doctype("Farm Plot", strict=True), "Farm Plot")

	def test_legacy_findings_are_not_mobile_mapped(self):
		self.assertNotIn("findings", api.STORE_TO_DOCTYPE)
		self.assertNotIn("Finding", api.ID_FIELD_MAP)

	def test_inspection_review_fields_are_server_owned(self):
		fields = api.MOBILE_SERVER_OWNED_FIELDS["Inspection"]
		self.assertIn("status", fields)
		self.assertIn("assigned_to", fields)
		self.assertIn("qa_reviewed_by", fields)
		self.assertIn("results", fields)
		self.assertIn("sampling_protocol_version", fields)
		self.assertIn("cumulative_total_plants", fields)

	def test_count_sampling_fields_have_mobile_contracts(self):
		self.assertEqual(
			api.MOBILE_FIELD_MAP["Inspection Take"]["totalPlantsCounted"],
			"total_plants_counted",
		)
		self.assertEqual(
			api.MOBILE_FIELD_MAP["Inspection Take Result"]["observedCount"],
			"observed_count",
		)
		self.assertEqual(
			api.MOBILE_FIELD_MAP["Inspection Result"]["incidencePercent"],
			"incidence_percent",
		)
		self.assertIn("Inspection Observation", api.MOBILE_FIELD_MAP)

	def test_agronomy_decisions_are_server_owned(self):
		fields = api.MOBILE_SERVER_OWNED_FIELDS["Agronomy Report"]
		self.assertIn("overall_result", fields)
		self.assertIn("pass_percentage", fields)
		self.assertIn("summary", fields)

		values = api._strip_server_owned_mobile_fields(
			"Agronomy Report",
			{
				"status": "Submitted",
				"overall_result": "Pass",
				"results": [
					{
						"parameter_code": "CROP_VIGOUR",
						"text_value": "Poor",
						"result_status": "Pass",
						"minimum_value": 0,
					}
				],
			},
		)
		self.assertNotIn("status", values)
		self.assertNotIn("overall_result", values)
		self.assertEqual(
			values["results"],
			[
				{
					"parameter_code": "CROP_VIGOUR",
					"text_value": "Poor",
					"value_captured": 1,
				}
			],
		)
