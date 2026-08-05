# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from naseco_fieldopsbackend.crop_cycle_lifecycle import (
	LIFECYCLE_STAGES,
	canonical_stage_name,
)
from naseco_fieldopsbackend.fixtures.seed_data import (
	seed_agronomy_activity_templates,
	seed_agronomy_report_templates,
)
from naseco_fieldopsbackend.uom import get_item_uom_conversion


def execute():
	seed_agronomy_report_templates()
	upgrade_recipes()
	seed_agronomy_activity_templates()
	backfill_input_uom_conversions()
	backfill_corrective_action_sources()
	initialize_existing_crop_cycles()


def upgrade_recipes():
	for name in frappe.get_all("Crop Recipe", pluck="name"):
		recipe = frappe.get_doc("Crop Recipe", name)
		template_by_stage = {
			row.stage_name: row.name
			for row in frappe.get_all(
				"Agronomy Report Template",
				fields=["name", "stage_name"],
			)
		}
		recipe.set("stages", [])
		for stage in LIFECYCLE_STAGES:
			recipe.append(
				"stages",
				{
					"stage_code": stage.code,
					"stage_name": stage.name,
					"order_index": stage.order,
					"start_day_offset": stage.start_day,
					"end_day_offset": stage.end_day,
					"duration_days": stage.end_day - stage.start_day + 1,
					"agronomy_report_template": template_by_stage.get(stage.name),
				},
			)
		for row in recipe.inputs:
			row.recipe_stage = canonical_stage_name(row.recipe_stage or row.input_type)
			if row.recipe_stage == "Field Verification & Contracting" and row.input_type == "Planting":
				row.recipe_stage = "Planting"
			stage = next(
				(item for item in LIFECYCLE_STAGES if item.name == row.recipe_stage),
				None,
			)
			if stage:
				row.stage_index = stage.order
		recipe.save(ignore_permissions=True)


def backfill_input_uom_conversions():
	for row in frappe.get_all(
		"Recipe Input Item",
		filters={"resource_type": "Stock Item"},
		fields=["name", "item_code", "unit", "quantity_per_acre"],
	):
		if not row.item_code:
			continue
		conversion = get_item_uom_conversion(row.item_code, row.unit)
		frappe.db.set_value(
			"Recipe Input Item",
			row.name,
			{
				"unit": conversion.uom,
				"stock_uom": conversion.stock_uom,
				"conversion_factor": conversion.conversion_factor,
				"stock_quantity_per_acre": (
					flt(row.quantity_per_acre) * flt(conversion.conversion_factor)
				),
			},
			update_modified=False,
		)

	for row in frappe.get_all(
		"Stage Input Request Item",
		fields=[
			"name",
			"item_code",
			"uom",
			"requested_qty",
			"approved_qty",
			"issued_qty",
		],
	):
		if not row.item_code:
			continue
		conversion = get_item_uom_conversion(row.item_code, row.uom)
		issued_stock_qty = flt(row.issued_qty) * flt(conversion.conversion_factor)
		frappe.db.set_value(
			"Stage Input Request Item",
			row.name,
			{
				"uom": conversion.uom,
				"stock_uom": conversion.stock_uom,
				"conversion_factor": conversion.conversion_factor,
				"requested_stock_qty": flt(row.requested_qty) * conversion.conversion_factor,
				"approved_stock_qty": flt(row.approved_qty) * conversion.conversion_factor,
				"issued_stock_qty": issued_stock_qty,
				"remaining_stock_qty": max(
					flt(row.approved_qty) * conversion.conversion_factor
					- issued_stock_qty,
					0,
				),
			},
			update_modified=False,
		)


def backfill_corrective_action_sources():
	for action in frappe.get_all(
		"Field Corrective Action",
		fields=["name", "inspection", "parameter"],
	):
		if not action.inspection:
			continue
		frappe.db.set_value(
			"Field Corrective Action",
			action.name,
			{
				"source_type": "Inspection",
				"source_name": action.inspection,
				"source_parameter": action.parameter,
			},
			update_modified=False,
		)


def initialize_existing_crop_cycles():
	from naseco_fieldopsbackend.inspection_scheduler import sync_crop_cycle_lifecycle

	for name in frappe.get_all("Crop Cycle", pluck="name"):
		sync_crop_cycle_lifecycle(frappe.get_doc("Crop Cycle", name))
