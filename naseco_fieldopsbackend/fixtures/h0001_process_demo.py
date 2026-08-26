"""Idempotent contract-to-harvest demo for outgrower H-0001, plot H-0001-C."""

import frappe
from frappe.utils import now_datetime, nowdate

from naseco_fieldopsbackend.fieldops_finance import FIELDOPS_ITEMS, create_crop_cycle_purchase_order, ensure_outgrower_supplier
from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle import confirm_planting_date

OUTGROWER = "H-0001"
PLOT = "H-0001-C"
CYCLE = "DEMO-H0001-C-2026B"
NOTE = "H-0001-C end-to-end FieldOps demonstration"


def execute():
	"""Create the coherent demo scenario and return all document identifiers."""
	frappe.set_user("Administrator")
	_validate_scope()
	try:
		contract = _contract(ensure_outgrower_supplier(OUTGROWER))
		cycle = _cycle(contract)
		confirm_planting_date(cycle.name, NOTE)
		cycle.reload()
		_mark_progress(cycle.name)
		_submit_planting_report(cycle)
		input_request = _input_request(cycle)
		advance = _advance(cycle)
		lot = _lot(cycle)
		order = _purchase_order(cycle)
		receipt = _purchase_receipt(cycle, lot, order)
		assessment = _assessment(cycle, lot, receipt)
		reject = _reject(assessment)
		settlement = _settlement(cycle)
		frappe.db.set_value("Crop Cycle", cycle.name, {"actual_harvest_date": nowdate(), "status": "COMPLETED"}, update_modified=False)
		frappe.db.set_value("Outgrower Production Contract", contract.name, "status", "Fulfilled", update_modified=False)
		frappe.db.commit()
		return _summary(contract, cycle, input_request, advance, lot, order, receipt, assessment, reject, settlement)
	except Exception:
		frappe.db.rollback()
		raise


def _validate_scope():
	for doctype, name in (("Outgrower", OUTGROWER), ("Farm Plot", PLOT), ("Season", "2026 B"), ("Crop Recipe", "Maize Production (Standard)"), ("Outgrower Pricing Policy", "2026B Maize Certified Seed Pricing")):
		if not frappe.db.exists(doctype, name):
			frappe.throw(f"Required demo master {doctype} {name} is missing.")
	if frappe.db.get_value("Farm Plot", PLOT, "outgrower") != OUTGROWER:
		frappe.throw(f"Farm Plot {PLOT} does not belong to {OUTGROWER}.")
	other = frappe.db.get_value("Crop Cycle", {"plot": PLOT, "name": ["!=", CYCLE]})
	if other:
		frappe.throw(f"Farm Plot {PLOT} is already used by Crop Cycle {other}.")


def _contract(supplier):
	name = frappe.db.get_value("Outgrower Production Contract", {"farm_plot": PLOT, "docstatus": 1})
	if name:
		return frappe.get_doc("Outgrower Production Contract", name)
	doc = frappe.get_doc({
		"doctype": "Outgrower Production Contract", "outgrower": OUTGROWER, "supplier": supplier,
		"farm_plot": PLOT, "season": "2026 B", "crop": "Maize", "variety": "Longe 10H",
		"production_category": "Certified", "crop_recipe": "Maize Production (Standard)",
		"pricing_policy": "2026B Maize Certified Seed Pricing", "agreement_date": "2026-07-15",
		"contract_start_date": "2026-07-15", "contract_end_date": "2027-01-31",
		"planting_start_date": "2026-07-20", "planting_end_date": "2026-08-10",
		"expected_harvest_date": "2026-11-30", "contracted_area_hectares": 0.40468564224,
		"parent_seed_item": FIELDOPS_ITEMS["Maize Seed (Hybrid)"]["item_code"],
		"planned_parent_seed_qty": 20, "parent_seed_uom": "Kg",
		"harvest_item": FIELDOPS_ITEMS["Maize Seed Harvest"]["item_code"], "expected_yield_qty": 1000,
		"contract_rate": 1600, "default_recovery_policy": "Fully Recoverable",
		"input_recovery_terms": "Recover approved inputs from accepted harvest value.",
		"quality_standard_terms": "<p>Apply NASECO seed-production and inspection standards.</p>",
		"company_obligations": "<p>Provide inputs, supervision, inspection and collection.</p>",
		"farmer_obligations": "<p>Maintain isolation, crop identity and field records.</p>",
		"supervisor_obligations": "<p>Complete scheduled field activities and reports.</p>",
		"termination_terms": "<p>Material non-compliance may terminate the agreement.</p>",
		"required_isolation_quality": "Adequate", "is_signed": 1, "signed_on": "2026-07-15 10:00:00",
		"company_signatory": "Administrator", "remarks": NOTE,
	}).insert(ignore_permissions=True)
	doc.submit()
	return doc


def _cycle(contract):
	if frappe.db.exists("Crop Cycle", CYCLE):
		return frappe.get_doc("Crop Cycle", CYCLE)
	return frappe.get_doc({"doctype": "Crop Cycle", "crop_cycle_id": CYCLE, "production_contract": contract.name, "planting_date": "2026-07-25", "planting_confirmation_notes": NOTE}).insert(ignore_permissions=True)


def _mark_progress(cycle):
	for row in frappe.get_all("Stage Activity", filters={"crop_cycle": cycle}, fields=["name"], order_by="due_date, name", limit_page_length=3):
		frappe.db.set_value("Stage Activity", row.name, {"status": "Completed", "completion_notes": NOTE, "completed_on": now_datetime()}, update_modified=False)


def _submit_planting_report(cycle):
	from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report import set_agronomy_raw_value

	name = frappe.db.get_value("Agronomy Report", {"crop_cycle": cycle.name, "report_number": 2, "docstatus": ["<", 2]})
	if not name:
		return
	report = frappe.get_doc("Agronomy Report", name)
	if report.docstatus == 1:
		return
	values = {"PLANTING_DATE": cycle.planting_date, "PLANTED_AREA": 1, "SEED_QUANTITY": 20,
		"MALE_FEMALE_RATIO": "1:4", "PLANTING_METHOD": "Hand planting", "BASAL_FERTILIZER": "Yes"}
	for row in report.results:
		set_agronomy_raw_value(row, values.get(row.parameter_code))
		report.remarks = NOTE
	report.update({"report_date": cycle.planting_date, "latitude": 2.08175, "longitude": 32.90287,
		"gps_accuracy_meters": 2.5, "inside_plot_boundary": 1,
		"location_captured_at": f"{cycle.planting_date} 09:30:00", "field_notes": NOTE})
	report.save(ignore_permissions=True)
	report.submit()


def _input_request(cycle):
	name = frappe.db.get_value("Stage Input Request", {"crop_cycle": cycle.name})
	if name:
		return frappe.get_doc("Stage Input Request", name)
	stage = frappe.db.get_value("Crop Cycle Stage", {"crop_cycle": cycle.name, "stage_name": "Planting"})
	plan = next((row for row in cycle.planned_inputs if row.item_code), None)
	item = plan.item_code if plan else FIELDOPS_ITEMS["Maize Seed (Hybrid)"]["item_code"]
	qty = plan.planned_qty if plan and plan.planned_qty else 20
	doc = frappe.get_doc({
		"doctype": "Stage Input Request", "request_id": "DEMO-H0001-C-INPUT-01", "crop_cycle": cycle.name,
		"stage": stage, "request_date": "2026-07-18", "required_by": "2026-07-23",
		"source_warehouse": "Stores - NS", "notes": NOTE,
		"items": [{"item_code": item, "requested_qty": qty, "approved_qty": qty,
			"uom": plan.uom if plan else "Kg", "source_warehouse": "Stores - NS",
			"recovery_policy": "Fully Recoverable", "recoverable_percent": 100,
			"recovery_rate_basis": "Contract Rate", "contract_recovery_rate": plan.forecast_recovery_rate if plan else 12000}],
	}).insert(ignore_permissions=True)
	doc.submit()
	return doc


def _advance(cycle):
	name = frappe.db.get_value("Crop Cycle Advance Request", {"crop_cycle": cycle.name, "purpose": ["like", f"%{NOTE}%"]})
	if name:
		return frappe.get_doc("Crop Cycle Advance Request", name)
	return frappe.get_doc({"doctype": "Crop Cycle Advance Request", "crop_cycle": cycle.name,
		"request_date": "2026-07-18", "purpose": f"Planting labour — {NOTE}",
		"requested_amount": 150000, "approved_amount": 100000}).insert(ignore_permissions=True)


def _lot(cycle):
	name = frappe.db.get_value("Crop Production Lot", {"crop_cycle": cycle.name, "lot_number": 1})
	if name:
		return frappe.get_doc("Crop Production Lot", name)
	return frappe.get_doc({"doctype": "Crop Production Lot", "lot_number": 1, "crop_cycle": cycle.name,
		"planting_start_date": "2026-07-25", "planting_end_date": "2026-07-26", "area_hectares": 0.40468564224,
		"accepted_area_hectares": 0.38445136013, "rejected_area_hectares": 0.02023428211, "parent_seed_qty": 20,
		"parent_seed_uom": "Kg", "crib_ready_date": nowdate(), "status": "Harvest Ready",
		"field_notes": NOTE}).insert(ignore_permissions=True)


def _purchase_order(cycle):
	doc = frappe.get_doc("Purchase Order", create_crop_cycle_purchase_order(cycle.name))
	if doc.docstatus == 0:
		doc.submit()
	return doc


def _purchase_receipt(cycle, lot, order):
	name = frappe.db.get_value("Purchase Receipt", {"custom_production_contract": cycle.production_contract, "remarks": NOTE})
	if name:
		return frappe.get_doc("Purchase Receipt", name)
	order_item = order.items[0]
	doc = frappe.get_doc({
		"doctype": "Purchase Receipt", "supplier": order.supplier, "company": order.company,
		"posting_date": nowdate(), "set_warehouse": "Harvest Quarantine - NS",
		"custom_outgrower": OUTGROWER, "custom_production_contract": cycle.production_contract,
		"crop_cycle": cycle.name, "remarks": NOTE,
		"items": [{"item_code": cycle.harvest_item, "qty": 900, "rate": cycle.contract_rate,
			"warehouse": "Harvest Quarantine - NS", "purchase_order": order.name,
			"purchase_order_item": order_item.name, "crop_cycle": cycle.name,
			"custom_production_lot": lot.name}],
	}).insert(ignore_permissions=True)
	doc.submit()
	return doc


def _assessment(cycle, lot, receipt):
	name = frappe.db.get_value("Seed Harvest Quality Assessment", {"production_lot": lot.name, "docstatus": ["<", 2]})
	if name:
		return frappe.get_doc("Seed Harvest Quality Assessment", name)
	row = receipt.items[0]
	doc = frappe.get_doc({
		"doctype": "Seed Harvest Quality Assessment", "production_lot": lot.name,
		"purchase_receipt": receipt.name, "purchase_receipt_item": row.name, "item_code": row.item_code,
		"delivery_date": nowdate(), "gross_qty": row.stock_qty, "uom": row.stock_uom,
		"moisture_percent": 14, "germination_percent": 94, "genetic_purity_percent": 98.5,
		"vigor_percent": 92, "undersize_percent": 2, "reject_percent": 5, "disposition": "Seed",
		"inspected_by": "Administrator", "verified_by": "Administrator",
		"quality_decision_notes": "Low germination demonstrates grain downgrade; five percent is isolated for reject handling.",
	}).insert(ignore_permissions=True)
	from frappe.utils.file_manager import save_file
	file = save_file("H-0001-C-demo-lab-certificate.txt", b"DEMO result: germination 94%, genetic purity 98.5%, moisture 14%.", doc.doctype, doc.name, is_private=1)
	doc.laboratory_certificate = file.file_url
	doc.save(ignore_permissions=True)
	doc.submit()
	return doc


def _reject(assessment):
	name = frappe.db.get_value("Harvest Reject Disposition", {"quality_assessment": assessment.name})
	if name:
		return frappe.get_doc("Harvest Reject Disposition", name)
	doc = frappe.get_doc({"doctype": "Harvest Reject Disposition", "quality_assessment": assessment.name,
		"rejected_qty": 40, "reject_reason": "Contamination", "disposition": "Hold for Retest",
		"source_warehouse": "Harvest Quarantine - NS", "target_warehouse": "Harvest Rejects - NS",
		"notes": NOTE}).insert(ignore_permissions=True)
	doc.submit()
	return doc


def _settlement(cycle):
	name = frappe.db.get_value("Crop Cycle Settlement", {"crop_cycle": cycle.name, "docstatus": 0})
	if name:
		return frappe.get_doc("Crop Cycle Settlement", name)
	return frappe.get_doc({"doctype": "Crop Cycle Settlement", "crop_cycle": cycle.name,
		"posting_date": nowdate(), "notes": NOTE}).insert(ignore_permissions=True)


def _summary(contract, cycle, request, advance, lot, order, receipt, assessment, reject, settlement):
	return {"outgrower": OUTGROWER, "plot": PLOT, "production_contract": contract.name,
		"crop_cycle": cycle.name, "input_request": request.name, "material_request": request.material_request,
		"advance_request": advance.name, "production_lot": lot.name, "purchase_order": order.name,
		"purchase_receipt": receipt.name, "quality_assessment": assessment.name,
		"reject_disposition": reject.name, "reject_stock_entry": reject.stock_entry,
		"settlement": settlement.name,
		"agronomy_activities": frappe.db.count("Stage Activity", {"crop_cycle": cycle.name}),
		"agronomy_reports": frappe.db.count("Agronomy Report", {"crop_cycle": cycle.name}),
		"inspections": frappe.db.count("Inspection", {"crop_cycle": cycle.name})}
