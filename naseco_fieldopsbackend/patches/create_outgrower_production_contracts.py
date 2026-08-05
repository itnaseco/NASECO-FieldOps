# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, getdate, now_datetime

from naseco_fieldopsbackend.fieldops_finance import (
	ensure_erpnext_custom_fields,
	ensure_outgrower_supplier,
	get_default_company,
)


def execute():
	ensure_erpnext_custom_fields()
	if not frappe.db.exists("DocType", "Outgrower Production Contract"):
		return

	for cycle_name in frappe.get_all(
		"Crop Cycle",
		filters={"production_contract": ["is", "not set"]},
		pluck="name",
	):
		migrate_crop_cycle(cycle_name)

	backfill_operational_documents()


def migrate_crop_cycle(cycle_name):
	cycle = frappe.get_doc("Crop Cycle", cycle_name)
	plot = frappe.get_doc("Farm Plot", cycle.plot)
	supplier = cycle.supplier or frappe.db.get_value("Outgrower", plot.outgrower, "supplier")
	if not supplier:
		supplier = ensure_outgrower_supplier(plot.outgrower)

	recorded_start = cycle.start_date or cycle.planting_date or frappe.utils.nowdate()
	planting_start = cycle.planting_date or recorded_start
	start_date = min(getdate(recorded_start), getdate(planting_start))
	harvest_date = max(
		getdate(cycle.expected_harvest_date or add_days(planting_start, 150)),
		getdate(planting_start),
	)
	planting_end = min(getdate(add_days(planting_start, 30)), harvest_date)
	contract_end = add_days(harvest_date, 30)
	recipe = cycle.recipe or frappe.db.get_value("Crop Recipe", {"crop": cycle.crop}, "name")

	contract = frappe.get_doc(
		{
			"doctype": "Outgrower Production Contract",
			"outgrower": plot.outgrower,
			"supplier": supplier,
			"company": cycle.company or get_default_company(),
			"farm_plot": cycle.plot,
			"season": cycle.season,
			"crop": cycle.crop,
			"variety": cycle.variety,
			"production_category": cycle.production_category or "Certified",
			"crop_recipe": recipe,
			"contract_start_date": start_date,
			"contract_end_date": contract_end,
			"planting_start_date": planting_start,
			"planting_end_date": planting_end,
			"expected_harvest_date": harvest_date,
			"harvest_item": cycle.harvest_item,
			"harvest_uom": cycle.harvest_uom,
			"expected_yield_qty": cycle.expected_yield_qty or 1,
			"pricing_method": "Fixed Rate",
			"contract_rate": cycle.contract_rate or 1,
			"max_exposure_percent": cycle.max_exposure_percent or 70,
			"default_recovery_policy": "Fully Recoverable",
			"input_recovery_terms": (
				"Approved stock inputs and supplier advances are recoverable from the "
				"accepted harvest value for this crop cycle."
			),
			"minimum_farmer_compliance_percent": 80,
			"minimum_supervisor_compliance_percent": 80,
			"required_isolation_quality": "Good",
			"target_take_spacing_m": 5,
			"quality_standard_terms": (
				"<p>Quality inspections follow the approved stage-specific FieldOps "
				"inspection standards. Scores below 50% are Non-Compliant, 50% through "
				"80% require Improvement, and scores above 80% are Compliant.</p>"
			),
			"farmer_obligations": (
				"<p>Maintain the contracted field, crop identity, isolation, records and "
				"access required for agronomy supervision and quality inspections.</p>"
			),
			"supervisor_obligations": (
				"<p>Schedule and verify stage activities, inputs, corrective actions and "
				"field records throughout the crop cycle.</p>"
			),
			"termination_terms": (
				"<p>The company may suspend or terminate production for material breach, "
				"failed corrective action, loss of crop identity or non-compliance.</p>"
			),
			"is_signed": 1,
			"signed_on": now_datetime(),
			"company_signatory": "Administrator",
		}
	)
	contract.flags.ignore_mandatory = True
	contract.insert(ignore_permissions=True)
	contract.submit()

	frappe.db.set_value(
		"Crop Cycle",
		cycle.name,
		"production_contract",
		contract.name,
		update_modified=False,
	)
	contract.db_set("linked_crop_cycle", cycle.name, update_modified=False)


def backfill_operational_documents():
	for doctype in (
		"Stage Input Request",
		"Crop Cycle Advance Request",
		"Crop Cycle Settlement",
		"Inspection",
	):
		if not frappe.db.exists("DocType", doctype):
			continue
		for row in frappe.get_all(
			doctype,
			filters={"production_contract": ["is", "not set"]},
			fields=["name", "crop_cycle"],
		):
			production_contract = frappe.db.get_value(
				"Crop Cycle",
				row.crop_cycle,
				"production_contract",
			)
			if production_contract:
				frappe.db.set_value(
					doctype,
					row.name,
					"production_contract",
					production_contract,
					update_modified=False,
				)

	for doctype, source_field in (
		("Material Request", "custom_stage_input_request"),
		("Stock Entry", "custom_stage_input_request"),
		("Payment Entry", "custom_crop_cycle_advance_request"),
		("Purchase Invoice", "custom_crop_cycle_settlement"),
	):
		for row in frappe.get_all(
			doctype,
			filters={
				source_field: ["is", "set"],
				"custom_production_contract": ["is", "not set"],
			},
			fields=["name", source_field],
		):
			source_doctype = {
				"custom_stage_input_request": "Stage Input Request",
				"custom_crop_cycle_advance_request": "Crop Cycle Advance Request",
				"custom_crop_cycle_settlement": "Crop Cycle Settlement",
			}[source_field]
			production_contract = frappe.db.get_value(
				source_doctype,
				row.get(source_field),
				"production_contract",
			)
			if production_contract:
				frappe.db.set_value(
					doctype,
					row.name,
					"custom_production_contract",
					production_contract,
					update_modified=False,
				)

	for cycle in frappe.get_all(
		"Crop Cycle",
		filters={"purchase_order": ["is", "set"]},
		fields=["purchase_order", "production_contract"],
	):
		if cycle.production_contract:
			frappe.db.set_value(
				"Purchase Order",
				cycle.purchase_order,
				"custom_production_contract",
				cycle.production_contract,
				update_modified=False,
			)
