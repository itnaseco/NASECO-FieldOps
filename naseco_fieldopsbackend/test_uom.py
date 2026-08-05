from unittest import TestCase
from unittest.mock import patch

from naseco_fieldopsbackend import api
from naseco_fieldopsbackend.uom import normalize_uom


class TestUOMNormalization(TestCase):
	def test_normalizes_legacy_fieldops_units(self):
		self.assertEqual(normalize_uom("kg"), "Kg")
		self.assertEqual(normalize_uom("L"), "Litre")
		self.assertEqual(normalize_uom("acres"), "Acre")
		self.assertEqual(normalize_uom("%"), "Percent")
		self.assertEqual(normalize_uom("pieces"), "Nos")
		self.assertEqual(normalize_uom("person-days"), "Person Day")

	def test_preserves_unknown_uom(self):
		self.assertEqual(normalize_uom("Custom Agronomy Unit"), "Custom Agronomy Unit")
		self.assertEqual(normalize_uom(""), "")
		self.assertIsNone(normalize_uom(None))

	def test_mobile_unit_contract_uses_uom(self):
		self.assertEqual(api.STORE_TO_DOCTYPE["units"], "UOM")
		self.assertEqual(api.STORE_TO_DOCTYPE["Unit"], "UOM")
		self.assertEqual(api.DOCTYPE_TO_STORE["UOM"], "units")
		self.assertEqual(api.MOBILE_FIELD_MAP["UOM"]["unitName"], "uom_name")
		self.assertEqual(api._map_doc_to_mobile("UOM", {"uom_name": "Kg"}), {"unitName": "Kg"})
		self.assertEqual(
			api._normalize_uom_doc_data({"doctype": "Unit", "name": "kg", "unit_name": "kg"}),
			{"doctype": "UOM", "name": "Kg", "uom_name": "Kg"},
		)

	@patch.object(api.frappe, "get_all", return_value=[{"name": "Kg", "uom_name": "Kg"}])
	def test_reference_data_preserves_legacy_unit_key(self, _get_all):
		method = api.get_reference_data
		while hasattr(method, "__wrapped__"):
			method = method.__wrapped__
		with patch.object(api, "_get_mobile_positioning_settings", return_value={}):
			result = method()
		self.assertTrue(result["success"])
		self.assertIn("Unit", result["reference_data"])
		self.assertNotIn("UOM", result["reference_data"])
		self.assertEqual(result["reference_data"]["Unit"][0]["unit_name"], "Kg")
		self.assertEqual(result["reference_data"]["Unit"][0]["unitName"], "Kg")
