import frappe
from frappe.utils import add_days, getdate

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season import (
	get_season_status,
	update_season_statuses,
)


SEASON_2026_B = {
	"doctype": "Season",
	"name": "2026 B",
	"season_name": "2026 B",
	"season_id": "season_2026_b",
	"start_date": "2026-07-15",
	"end_date": "2027-01-31",
}


def execute():
	"""Ensure the versioned 2026 B season can coexist with older cloud data."""
	_close_prior_overlaps()
	ensure_2026_b_season()
	update_season_statuses()


def _close_prior_overlaps():
	start_date = getdate(SEASON_2026_B["start_date"])
	end_date = getdate(SEASON_2026_B["end_date"])
	for season in frappe.get_all(
		"Season",
		filters={
			"name": ["!=", SEASON_2026_B["name"]],
			"start_date": ["<=", end_date],
			"end_date": [">=", start_date],
		},
		fields=["name", "start_date", "end_date"],
	):
		if getdate(season.start_date) < start_date <= getdate(season.end_date):
			frappe.db.set_value(
				"Season",
				season.name,
				"end_date",
				add_days(start_date, -1),
				update_modified=False,
			)


def ensure_2026_b_season():
	values = {
		"season_name": SEASON_2026_B["season_name"],
		"season_id": SEASON_2026_B["season_id"],
		"start_date": SEASON_2026_B["start_date"],
		"end_date": SEASON_2026_B["end_date"],
		"season_status": get_season_status(
			SEASON_2026_B["start_date"],
			SEASON_2026_B["end_date"],
		),
	}
	if frappe.db.exists("Season", SEASON_2026_B["name"]):
		frappe.db.set_value(
			"Season",
			SEASON_2026_B["name"],
			values,
			update_modified=False,
		)
		return

	frappe.get_doc({**SEASON_2026_B, **values}).insert(ignore_permissions=True)
