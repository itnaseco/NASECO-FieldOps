# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe

from naseco_fieldopsbackend.inspection_scheduler import update_crop_cycle_current_stage


def update_active_crop_cycle_stages():
	"""Daily stage pointer refresh for active and planned crop cycles."""
	for crop_cycle in frappe.get_all(
		"Crop Cycle",
		filters={"status": ["in", ["PLANNED", "ACTIVE"]]},
		pluck="name",
	):
		update_crop_cycle_current_stage(crop_cycle)
