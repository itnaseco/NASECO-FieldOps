from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_advance_request.crop_cycle_advance_request import (
	CropCycleAdvanceRequest,
)


class TestCropCycleAdvanceRequest(TestCase):
	def test_accepts_approved_amount_within_exposure_capacity(self):
		request = SimpleNamespace(
			requested_amount=1_000_000,
			approved_amount=750_000,
			available_advance_capacity=800_000,
			currency="UGX",
			docstatus=0,
		)

		CropCycleAdvanceRequest.validate_amounts(request)

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_advance_request.crop_cycle_advance_request.frappe.throw",
		side_effect=frappe.ValidationError,
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_advance_request.crop_cycle_advance_request.frappe.format_value",
		side_effect=lambda value, _options: str(value),
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_advance_request.crop_cycle_advance_request._",
		side_effect=lambda message: message,
	)
	def test_rejects_approved_amount_above_exposure_capacity(
		self,
		_translate,
		_format_value,
		_throw,
	):
		request = SimpleNamespace(
			requested_amount=1_000_000,
			approved_amount=900_000,
			available_advance_capacity=800_000,
			currency="UGX",
			docstatus=0,
		)

		with self.assertRaises(frappe.ValidationError):
			CropCycleAdvanceRequest.validate_amounts(request)
