# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime


def execute():
	"""Preserve lifecycle state for cycles scheduled before confirmation existed."""
	frappe.db.sql(
		"""
		update `tabCrop Cycle`
		set planting_date_confirmed = 1,
			planting_date_confirmed_by = coalesce(owner, 'Administrator'),
			planting_date_confirmed_on = coalesce(modified, %s),
			planting_confirmation_notes = coalesce(
				planting_confirmation_notes,
				'Backfilled from existing generated lifecycle schedules.'
			)
		where planting_date is not null
			and planting_date_confirmed = 0
			and (
				lifecycle_initialized = 1
				or inspection_schedule_generated = 1
				or agronomy_schedule_generated = 1
				or agronomy_report_schedule_generated = 1
			)
		""",
		(now_datetime(),),
	)
