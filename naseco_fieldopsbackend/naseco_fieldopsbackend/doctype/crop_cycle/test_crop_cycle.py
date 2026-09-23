# Copyright (c) 2026, Naseco and Contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle import CropCycle
from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle import farm_plot_status_for_cycle
from naseco_fieldopsbackend.inspection_scheduler import resolve_activity_templates
from naseco_fieldopsbackend.inspection_scheduler import sync_crop_cycle_lifecycle
from naseco_fieldopsbackend.inspection_scheduler import update_crop_cycle_current_stage
from naseco_fieldopsbackend.inspection_scheduler import inspection_lifecycle_stage_name
from naseco_fieldopsbackend.inspection_scheduler import resolve_inspection_templates


class TestCropCycle(TestCase):
	def test_planned_and_running_cycles_reserve_the_plot(self):
		self.assertEqual(farm_plot_status_for_cycle("PLANNED"), "Active")
		self.assertEqual(farm_plot_status_for_cycle("ACTIVE"), "Active")

	def test_completed_cycle_releases_the_plot(self):
		self.assertEqual(farm_plot_status_for_cycle("COMPLETED"), "Idle")

	def test_flowering_inspections_map_to_flowering_lifecycle_stage(self):
		for inspection_type in ("1st Flowering", "2nd Flowering", "3rd Flowering"):
			self.assertEqual(
				inspection_lifecycle_stage_name(inspection_type),
				"Flowering",
			)
		self.assertEqual(
			inspection_lifecycle_stage_name("Pre-flowering"),
			"Pre-flowering",
		)
		self.assertEqual(
			inspection_lifecycle_stage_name("Pre-harvest"),
			"Pre-harvest",
		)

	@patch("naseco_fieldopsbackend.inspection_scheduler.frappe.db.set_value")
	@patch("naseco_fieldopsbackend.inspection_scheduler.frappe.db.get_value")
	@patch("naseco_fieldopsbackend.inspection_scheduler.frappe.get_all")
	def test_completed_vegetative_stage_advances_without_regression(
		self, get_all, get_value, set_value
	):
		get_all.return_value = [
			frappe._dict(name="FIELD", order_index=1, status="Pending", start_date=None, end_date=None),
			frappe._dict(name="PLANTING", order_index=2, status="Completed", start_date=None, end_date=None),
			frappe._dict(name="EMERGENCE", order_index=3, status="Completed", start_date=None, end_date=None),
			frappe._dict(name="VEGETATIVE", order_index=4, status="Completed", start_date=None, end_date=None),
			frappe._dict(name="PRE-FLOWERING", order_index=5, status="Pending", start_date=None, end_date=None),
		]
		get_value.return_value = "FIELD"

		with patch(
			"naseco_fieldopsbackend.inspection_scheduler.nowdate",
			return_value="2026-09-17",
		):
			update_crop_cycle_current_stage("CC-TEST")

		set_value.assert_any_call(
			"Crop Cycle",
			"CC-TEST",
			"current_stage",
			"PRE-FLOWERING",
			update_modified=False,
		)

	@patch("naseco_fieldopsbackend.inspection_scheduler.ensure_crop_cycle_stages")
	def test_lifecycle_is_not_generated_before_planting_confirmation(self, ensure_stages):
		cycle = frappe._dict(name="CC-TEST", planting_date_confirmed=0)

		result = sync_crop_cycle_lifecycle(cycle)

		self.assertIsNone(result)
		ensure_stages.assert_not_called()

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle.frappe.get_doc"
	)
	def test_contract_terms_override_cycle_values(self, get_doc):
		get_doc.return_value = frappe._dict(
			{
				"name": "OPC-2026-00001",
				"docstatus": 1,
				"status": "Active",
				"linked_crop_cycle": None,
				"farm_plot": "PLOT-001",
				"crop": "Maize",
				"variety": "Longe 10H",
				"season": "Season A 2026",
				"crop_recipe": "Maize Production (Standard)",
				"company": "Naseco Seeds",
				"supplier": "SAMPLE-SUPPLIER",
				"harvest_item": "FO-MAIZE-SEED-HARVEST",
				"harvest_uom": "Kg",
				"expected_yield_qty": 5000,
				"contract_rate": 2500,
				"currency": "UGX",
				"expected_harvest_value": 12500000,
				"max_exposure_percent": 70,
				"production_category": "Certified",
				"planting_start_date": "2026-03-01",
				"expected_harvest_date": "2026-07-25",
			}
		)
		cycle = SimpleNamespace(
			name="CYCLE-NEW",
			production_contract="OPC-2026-00001",
			contract_rate=1,
		)
		cycle.set = lambda fieldname, value: setattr(cycle, fieldname, value)

		CropCycle.apply_contract_terms(cycle)

		self.assertEqual(cycle.contract_rate, 2500)
		self.assertEqual(cycle.plot, "PLOT-001")
		self.assertEqual(cycle.production_category, "Certified")

	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle.frappe.throw",
		side_effect=frappe.ValidationError,
	)
	@patch(
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle._",
		side_effect=lambda message: message,
	)
	@patch("naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle.get_existing_cycle_for_plot")
	def test_rejects_second_crop_cycle_for_plot(self, get_value, _translate, _throw):
		get_value.return_value = frappe._dict(
			{"name": "CYCLE-EXISTING", "crop_cycle_id": "CYCLE-EXISTING"}
		)
		cycle = SimpleNamespace(name="CYCLE-NEW", plot="PLOT-001")

		with self.assertRaises(frappe.ValidationError):
			CropCycle.validate_single_cycle_per_plot(cycle)

	@patch("naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle.get_existing_cycle_for_plot")
	def test_allows_first_crop_cycle_for_plot(self, get_value):
		get_value.return_value = None
		cycle = SimpleNamespace(name="CYCLE-NEW", plot="PLOT-001")

		CropCycle.validate_single_cycle_per_plot(cycle)


class TestInspectionTemplateResolution(TestCase):
	def test_accepts_published_and_legacy_active_templates(self):
		templates = [
			frappe._dict(name="Published", lifecycle_status="Published"),
			frappe._dict(name="Legacy", lifecycle_status=None),
			frappe._dict(name="Draft", lifecycle_status="Draft"),
			frappe._dict(name="Retired", lifecycle_status="Retired"),
		]

		resolved = resolve_inspection_templates(templates)

		self.assertEqual([row.name for row in resolved], ["Published", "Legacy"])


class TestAgronomyActivityTemplateResolution(TestCase):
	@patch("naseco_fieldopsbackend.inspection_scheduler.frappe.db.get_value")
	def test_uses_inherited_recipe_templates_before_same_crop_fallback(self, get_value):
		def values(doctype, name, fieldname):
			if fieldname == "based_on_recipe":
				return {"VARIETY": "BASE", "BASE": None}.get(name)
			return {"OTHER": "Maize"}.get(name)

		get_value.side_effect = values
		templates = [
			frappe._dict(name="Generic", crop_recipe=None),
			frappe._dict(name="Base Activity", crop_recipe="BASE"),
			frappe._dict(name="Other Maize Activity", crop_recipe="OTHER"),
		]
		cycle = frappe._dict(recipe="VARIETY", crop="Maize")

		resolved = resolve_activity_templates(cycle, templates)

		self.assertEqual([row.name for row in resolved], ["Generic", "Base Activity"])

	@patch("naseco_fieldopsbackend.inspection_scheduler.frappe.db.get_value")
	def test_falls_back_to_templates_for_the_same_crop(self, get_value):
		def values(doctype, name, fieldname):
			if fieldname == "based_on_recipe":
				return None
			return {"MAIZE-BASE": "Maize", "RICE-BASE": "Rice"}.get(name)

		get_value.side_effect = values
		templates = [
			frappe._dict(name="Generic", crop_recipe=None),
			frappe._dict(name="Maize Activity", crop_recipe="MAIZE-BASE"),
			frappe._dict(name="Rice Activity", crop_recipe="RICE-BASE"),
		]
		cycle = frappe._dict(recipe="NEW-MAIZE", crop="Maize")

		resolved = resolve_activity_templates(cycle, templates)

		self.assertEqual([row.name for row in resolved], ["Generic", "Maize Activity"])
