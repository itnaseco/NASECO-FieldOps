import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

import frappe

from naseco_fieldopsbackend.crop_cycle_lifecycle import STAGE_NAMES, canonical_stage_name
from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report import (
	AgronomyReport,
	evaluate_agronomy_result,
	has_raw_value,
	point_inside_polygon,
	set_agronomy_raw_value,
)


class TestAgronomyReport(unittest.TestCase):
	@patch("naseco_fieldopsbackend.inspection_scheduler.update_crop_cycle_current_stage")
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report.frappe.db.sql"
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report.frappe.db.set_value"
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report.frappe.get_all"
	)
	def test_submitted_report_completes_every_stage_activity(
		self, get_all, set_value, sql, update_current_stage
	):
		get_all.return_value = [
			SimpleNamespace(name="ACT-1", mandatory=1),
			SimpleNamespace(name="ACT-2", mandatory=0),
		]
		report = SimpleNamespace(
			name="AGR-TEST",
			stage="STAGE-TEST",
			crop_cycle="CYCLE-TEST",
		)

		AgronomyReport.complete_related_stage(report)

		activity_updates = [
			entry for entry in set_value.call_args_list if entry.args[0] == "Stage Activity"
		]
		self.assertEqual(len(activity_updates), 2)
		self.assertTrue(
			all(entry.args[2]["status"] == "Completed" for entry in activity_updates)
		)
		self.assertTrue(
			all(
				entry.args[2]["completed_by_report"] == "AGR-TEST"
				for entry in activity_updates
			)
		)
		stage_update = next(
			entry for entry in set_value.call_args_list if entry.args[0] == "Crop Cycle Stage"
		)
		self.assertEqual(stage_update.args[2]["completion_percentage"], 100)
		self.assertEqual(sql.call_count, 2)
		update_current_stage.assert_called_once_with("CYCLE-TEST")

	def test_lifecycle_has_nine_ordered_stages(self):
		self.assertEqual(len(STAGE_NAMES), 9)
		self.assertEqual(STAGE_NAMES[0], "Field Verification & Contracting")
		self.assertEqual(STAGE_NAMES[-1], "Delivery")

	def test_legacy_operations_map_to_lifecycle_stage(self):
		self.assertEqual(canonical_stage_name("Top Dressing"), "Vegetative")
		self.assertEqual(canonical_stage_name("Harvesting"), "Harvest")

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report.frappe.throw",
		side_effect=frappe.ValidationError,
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report._",
		side_effect=lambda message: message,
	)
	def test_mandatory_result_requires_raw_value_only(self, _translate, _throw):
		report = SimpleNamespace(
			results=[
				SimpleNamespace(
					mandatory=1,
					parameter_label="Crop vigour",
					data_type="Good/Poor",
					numeric_value=None,
					text_value="",
					date_value=None,
				)
			]
		)
		with self.assertRaises(frappe.ValidationError):
			AgronomyReport.validate_mandatory_results(report)

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report._",
		side_effect=lambda message: message,
	)
	def test_numeric_standard_is_evaluated_from_raw_value(self, _translate):
		row = self._result_row(
			data_type="Percent",
			numeric_value=80,
			comparison_rule="At Least",
			minimum_value=80,
			unit="Percent",
		)
		self.assertEqual(evaluate_agronomy_result(row)[0], "Pass")
		row.numeric_value = 79.9
		self.assertEqual(evaluate_agronomy_result(row)[0], "Fail")

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report._",
		side_effect=lambda message: message,
	)
	def test_qualitative_standard_is_evaluated_from_raw_value(self, _translate):
		row = self._result_row(
			data_type="Good/Poor",
			text_value="Good",
			comparison_rule="Good Is Pass",
		)
		self.assertEqual(evaluate_agronomy_result(row)[0], "Pass")
		row.text_value = "Poor"
		self.assertEqual(evaluate_agronomy_result(row)[0], "Fail")

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report._",
		side_effect=lambda message: message,
	)
	def test_informational_value_does_not_create_a_pass_or_fail(self, _translate):
		row = self._result_row(
			data_type="Number",
			numeric_value=25,
			evaluation_mode="Informational",
			comparison_rule=None,
		)
		self.assertEqual(evaluate_agronomy_result(row)[0], "Informational")

	def test_guided_values_are_stored_in_the_correct_raw_field(self):
		yes_no = self._result_row(data_type="Yes/No", options="")
		set_agronomy_raw_value(yes_no, "yes")
		self.assertEqual(yes_no.text_value, "Yes")
		self.assertEqual(yes_no.value_captured, 1)
		self.assertIsNone(yes_no.numeric_value)

		count = self._result_row(data_type="Count", options="")
		set_agronomy_raw_value(count, 12)
		self.assertEqual(count.numeric_value, 12)
		self.assertEqual(count.value_captured, 1)
		self.assertIsNone(count.text_value)

		selection = self._result_row(
			data_type="Select",
			options="Basic\nCertified",
		)
		set_agronomy_raw_value(selection, "certified")
		self.assertEqual(selection.text_value, "Certified")

		set_agronomy_raw_value(selection, None)
		self.assertEqual(selection.value_captured, 0)
		self.assertIsNone(selection.text_value)

	def test_guided_numeric_zero_is_distinct_from_an_uncaptured_value(self):
		row = self._result_row(data_type="Number", numeric_value=0, value_captured="0")
		self.assertFalse(has_raw_value(row))

		set_agronomy_raw_value(row, 0)
		self.assertTrue(has_raw_value(row))
		self.assertEqual(row.numeric_value, 0)

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report.now_datetime",
		return_value="2026-08-05 12:00:00",
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report._",
		side_effect=lambda message: message,
	)
	def test_critical_failure_overrides_weighted_pass_score(self, _translate, _now):
		passed = self._result_row(
			parameter_label="Crop vigour",
			data_type="Good/Poor",
			text_value="Good",
			comparison_rule="Good Is Pass",
			mandatory=1,
			severity="Standard",
			weight=9,
			corrective_action_on_fail=0,
			failure_action=None,
			corrective_action_due_days=3,
		)
		failed = self._result_row(
			parameter_label="Isolation quality",
			data_type="Good/Poor",
			text_value="Poor",
			comparison_rule="Good Is Pass",
			mandatory=1,
			severity="Critical",
			weight=1,
			corrective_action_on_fail=1,
			failure_action="Restore isolation.",
			corrective_action_due_days=1,
		)
		report = SimpleNamespace(
			results=[passed, failed],
			window_start_date="2026-08-01",
			window_end_date="2026-08-10",
			critical_failure_override=1,
			overall_pass_threshold_percent=80,
			report_date="2026-08-05",
			has_recorded_results=lambda: True,
			build_automated_summary=lambda failures, pending: "Automated summary",
		)

		AgronomyReport.evaluate_results(report)

		self.assertEqual(report.pass_percentage, 90)
		self.assertEqual(report.overall_result, "Fail")
		self.assertEqual(report.critical_failure_count, 1)
		self.assertEqual(report.corrective_action, "Isolation quality: Restore isolation.")
		self.assertEqual(str(report.corrective_action_due_date), "2026-08-06")

	def test_report_point_is_checked_against_plot_boundary(self):
		polygon = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
		self.assertEqual(point_inside_polygon(0.5, 0.5, polygon), 1)
		self.assertEqual(point_inside_polygon(2.0, 2.0, polygon), 0)

	@patch("naseco_fieldopsbackend.inspection_scheduler.sync_crop_cycle_lifecycle")
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report.frappe"
	)
	def test_planting_report_updates_contract_and_crop_cycle(
		self, frappe_mock, sync_lifecycle
	):
		cycle = SimpleNamespace(
			name="CC-0001",
			planting_date="2026-08-01",
			start_date="2026-08-01",
		)
		frappe_mock.get_doc.return_value = cycle
		report = SimpleNamespace(
			stage_name="Planting",
			report_number=2,
			production_contract="OPC-0001",
			crop_cycle="CC-0001",
			results=[
				SimpleNamespace(
					parameter_code="PLANTING_DATE",
					date_value="2026-08-05",
				)
			],
		)

		AgronomyReport.sync_actual_planting_date(report)

		self.assertEqual(
			frappe_mock.db.set_value.call_args_list,
			[
				call(
					"Outgrower Production Contract",
					"OPC-0001",
					"actual_planting_date",
					"2026-08-05",
				),
				call(
					"Crop Cycle",
					"CC-0001",
					{
						"planting_date": "2026-08-05",
						"start_date": "2026-08-05",
					},
				),
			],
		)
		self.assertEqual(cycle.planting_date, "2026-08-05")
		self.assertEqual(cycle.start_date, "2026-08-05")
		sync_lifecycle.assert_called_once_with(cycle)

	def _result_row(self, **values):
		defaults = {
			"parameter_label": "Parameter",
			"data_type": "Number",
			"numeric_value": None,
			"text_value": "",
			"date_value": None,
			"allow_not_applicable": 0,
			"evaluation_mode": "Rule Based",
			"comparison_rule": "At Least",
			"minimum_value": 0,
			"maximum_value": None,
			"expected_value": None,
			"unit": None,
			"options": "",
			"mandatory": 1,
			"severity": "Standard",
			"weight": 1,
			"corrective_action_on_fail": 0,
			"failure_action": None,
			"corrective_action_due_days": 3,
		}
		defaults.update(values)
		return SimpleNamespace(**defaults)
