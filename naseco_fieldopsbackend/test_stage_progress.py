from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from naseco_fieldopsbackend import stage_progress


class _Stage(SimpleNamespace):
	def get(self, key, default=None):
		return getattr(self, key, default)


class TestStageProgress(TestCase):
	def setUp(self):
		self.cycle = SimpleNamespace(name="CYCLE-1", current_stage="STAGE-1")
		self.stage = _Stage(
			name="STAGE-1",
			stage_name="Flowering",
			status="In Progress",
			modified="2026-09-25 08:00:00",
			agronomy_report="REPORT-1",
			order_index=4,
		)

	def test_pending_activity_report_review_and_active_visit_block_closure(self):
		def rows(doctype, **kwargs):
			return {
				"Stage Activity": [SimpleNamespace(name="ACT-1", title="Weeding", status="In Progress")],
				"Inspection": [SimpleNamespace(name="INS-1", inspection_type="Flowering", status="Awaiting QA Review")],
				"Field Visit": [SimpleNamespace(name="VISIT-1", visited_by="alice@example.com", status="in_progress")],
			}.get(doctype, [])

		report = SimpleNamespace(
			name="REPORT-1", report_number="AGR-1", stage_name="Flowering",
			status="Draft", docstatus=0,
		)
		with patch.object(stage_progress.frappe, "get_all", side_effect=rows):
			with patch.object(stage_progress.frappe.db, "get_value", return_value=report):
				result = stage_progress._stage_readiness(self.cycle, self.stage)

		self.assertFalse(result["ready"])
		self.assertEqual(len(result["blockers"]), 4)

	def test_only_completed_submitted_and_verified_work_is_ready(self):
		def rows(doctype, **kwargs):
			return {
				"Stage Activity": [SimpleNamespace(name="ACT-1", title="Weeding", status="Completed")],
				"Inspection": [SimpleNamespace(name="INS-1", inspection_type="Flowering", status="Verified")],
				"Field Visit": [],
			}.get(doctype, [])

		report = SimpleNamespace(
			name="REPORT-1", report_number="AGR-1", stage_name="Flowering",
			status="Submitted", docstatus=1,
		)
		with patch.object(stage_progress.frappe, "get_all", side_effect=rows):
			with patch.object(stage_progress.frappe.db, "get_value", return_value=report):
				result = stage_progress._stage_readiness(self.cycle, self.stage)

		self.assertTrue(result["ready"])
		self.assertEqual(result["blockers"], [])
