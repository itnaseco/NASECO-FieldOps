import frappe

TERMINAL_INSPECTION_STATUSES = ("Awaiting QA Review", "Verified", "Reinspection Required", "Cancelled")

def complete_stage_if_ready(stage, crop_cycle):
	if not stage or not crop_cycle: return False
	report = frappe.db.get_value("Crop Cycle Stage", stage, "agronomy_report")
	if not report or frappe.db.get_value("Agronomy Report", report, "docstatus") != 1: return False
	if frappe.db.count("Stage Activity", {"stage": stage, "mandatory": 1, "status": ["not in", ["Completed", "Cancelled"]]}): return False
	if frappe.db.count("Inspection", {"stage": stage, "status": ["not in", list(TERMINAL_INSPECTION_STATUSES)]}): return False
	frappe.db.set_value("Crop Cycle Stage", stage, {"status":"Completed", "completion_percentage":100}, update_modified=False)
	from naseco_fieldopsbackend.inspection_scheduler import update_crop_cycle_current_stage
	update_crop_cycle_current_stage(crop_cycle)
	return True
