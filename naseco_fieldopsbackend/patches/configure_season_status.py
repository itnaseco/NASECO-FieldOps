# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, getdate

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season import (
	update_season_statuses,
)


def execute():
	remove_unlinked_legacy_season()
	close_previous_season_before_2026_b()
	update_season_statuses()


def remove_unlinked_legacy_season():
	if not frappe.db.exists("Season", "Main Season"):
		return

	for doctype, fieldname in get_season_link_fields():
		if frappe.db.exists(doctype, {fieldname: "Main Season"}):
			return

	frappe.delete_doc("Season", "Main Season", ignore_permissions=True)


def get_season_link_fields():
	standard_fields = frappe.get_all(
		"DocField",
		filters={
			"fieldtype": "Link",
			"options": "Season",
			"parenttype": "DocType",
		},
		fields=["parent", "fieldname"],
		as_list=True,
	)
	custom_fields = frappe.get_all(
		"Custom Field",
		filters={"fieldtype": "Link", "options": "Season"},
		fields=["dt", "fieldname"],
		as_list=True,
	)
	return [*standard_fields, *custom_fields]


def close_previous_season_before_2026_b():
	if not frappe.db.exists("Season", "Season A 2026") or not frappe.db.exists("Season", "2026 B"):
		return

	season_b_start = frappe.db.get_value("Season", "2026 B", "start_date")
	season_a_dates = frappe.db.get_value(
		"Season",
		"Season A 2026",
		["start_date", "end_date"],
		as_dict=True,
	)
	if (
		season_b_start
		and season_a_dates
		and getdate(season_a_dates.start_date) < getdate(season_b_start) <= getdate(season_a_dates.end_date)
	):
		frappe.db.set_value(
			"Season",
			"Season A 2026",
			"end_date",
			add_days(season_b_start, -1),
			update_modified=False,
		)
