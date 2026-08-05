# Copyright (c) 2026, NASECO and contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_production_contract.outgrower_production_contract import (
	OutgrowerProductionContract,
	is_planting_window_within_season,
)


class TestOutgrowerProductionContract(TestCase):
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_production_contract.outgrower_production_contract.frappe.throw",
		side_effect=frappe.ValidationError,
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_production_contract.outgrower_production_contract._",
		side_effect=lambda message: message,
	)
	def test_rejects_invalid_contract_date_order(self, _translate, _throw):
		contract = SimpleNamespace(
			contract_start_date="2026-04-01",
			planting_start_date="2026-03-15",
			planting_end_date="2026-03-31",
			expected_harvest_date="2026-07-15",
			contract_end_date="2026-08-15",
		)

		with self.assertRaises(frappe.ValidationError):
			OutgrowerProductionContract.validate_dates(contract)

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_production_contract.outgrower_production_contract.frappe.throw",
		side_effect=frappe.ValidationError,
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_production_contract.outgrower_production_contract._",
		side_effect=lambda message: message,
	)
	def test_rejects_exposure_percent_over_one_hundred(self, _translate, _throw):
		contract = SimpleNamespace(
			expected_yield_qty=100,
			contract_rate=2500,
			max_exposure_percent=101,
			pricing_method="Fixed Rate",
			pricing_formula=None,
		)

		with self.assertRaises(frappe.ValidationError):
			OutgrowerProductionContract.validate_commercial_terms(contract)

	def test_accepts_planting_window_inside_selected_season(self):
		self.assertTrue(
			is_planting_window_within_season(
				"2026-07-15",
				"2027-01-31",
				"2026-08-01",
				"2026-08-20",
			)
		)

	def test_rejects_planting_window_outside_selected_season(self):
		self.assertFalse(
			is_planting_window_within_season(
				"2026-07-15",
				"2027-01-31",
				"2026-07-01",
				"2026-07-20",
			)
		)

	def test_preserves_unchanged_scope_on_submitted_historical_contract(self):
		values = {
			"season": "2026 B",
			"planting_start_date": "2026-06-29",
			"planting_end_date": "2026-07-29",
		}
		previous = SimpleNamespace(docstatus=1, get=values.get)
		contract = SimpleNamespace(
			docstatus=1,
			get=values.get,
			get_doc_before_save=lambda: previous,
		)

		self.assertTrue(
			OutgrowerProductionContract.has_unchanged_submitted_season_scope(contract)
		)

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_production_contract.outgrower_production_contract.require_outgrower_manager"
	)
	def test_before_submit_allows_contract_without_signatures(self, _require_manager):
		contract = SimpleNamespace(
			validate_outgrower_eligibility=lambda: None,
			sync_optional_signatures=lambda: None,
			validate_no_active_contract=lambda: None,
			status="Draft",
		)

		OutgrowerProductionContract.before_submit(contract)

		self.assertEqual(contract.status, "Active")

	def test_synchronizes_completed_optional_signatures(self):
		contract = SimpleNamespace(
			signatories=[
				SimpleNamespace(
					signatory_role="Outgrower Manager",
					full_name="Contract Manager",
					signature="/files/manager-signature.png",
					signed_at="2026-08-04 09:00:00",
					user="manager@example.com",
				)
			],
			is_signed=0,
			signed_on=None,
			company_signatory=None,
		)

		OutgrowerProductionContract.sync_optional_signatures(contract)

		self.assertEqual(contract.is_signed, 1)
		self.assertEqual(contract.signed_on, "2026-08-04 09:00:00")
		self.assertEqual(contract.company_signatory, "manager@example.com")
