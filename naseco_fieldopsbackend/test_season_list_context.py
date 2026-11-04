from unittest import TestCase
from unittest.mock import patch

import frappe
from naseco_fieldopsbackend.season_list_context import get_active_seasons


class TestSeasonListContext(TestCase):
	@patch("naseco_fieldopsbackend.season_list_context.frappe.has_permission", return_value=False)
	@patch("naseco_fieldopsbackend.season_list_context.frappe.get_list")
	def test_no_permission_discloses_no_context(self, get_list, permission):
		self.assertEqual(get_active_seasons(), [])
		get_list.assert_not_called()

	@patch("naseco_fieldopsbackend.season_list_context.frappe.has_permission", return_value=True)
	@patch("naseco_fieldopsbackend.season_list_context.frappe.get_list")
	def test_requires_active_submitted_plan_and_permission_filtered_season(self, get_list, permission):
		get_list.side_effect = [
			[frappe._dict(name="2026B", season_name="2026 B"), frappe._dict(name="OTHER")],
			[frappe._dict(season="2026B"), frappe._dict(season="2026B")],
		]
		self.assertEqual([s.name for s in get_active_seasons()], ["2026B"])
		filters = get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["docstatus"], 1)
		self.assertEqual(filters["status"], "Active")

	@patch("naseco_fieldopsbackend.season_list_context.frappe.has_permission", return_value=True)
	@patch("naseco_fieldopsbackend.season_list_context.frappe.get_list", return_value=[])
	def test_no_current_season_has_no_default(self, get_list, permission):
		self.assertEqual(get_active_seasons(), [])
		self.assertEqual(sum(call.args[0] == "Season" for call in get_list.call_args_list), 1)

