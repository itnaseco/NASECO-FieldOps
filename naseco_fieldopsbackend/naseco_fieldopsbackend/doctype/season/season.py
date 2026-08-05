# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class Season(Document):
	def before_validate(self):
		if self.start_date and self.end_date:
			self.season_status = get_season_status(self.start_date, self.end_date)

	def validate(self):
		self.validate_date_range()
		self.validate_no_overlap()

	def validate_date_range(self):
		if self.start_date and self.end_date and getdate(self.start_date) > getdate(self.end_date):
			frappe.throw(_("Season Start Date cannot be after End Date."))

	def validate_no_overlap(self):
		if not self.start_date or not self.end_date:
			return

		overlapping_season = frappe.db.get_value(
			"Season",
			{
				"name": ["!=", self.name or ""],
				"start_date": ["<=", self.end_date],
				"end_date": [">=", self.start_date],
			},
			"name",
		)
		if overlapping_season:
			frappe.throw(
				_("Season dates overlap with {0}. Only one Season may cover a given date.").format(
					frappe.bold(overlapping_season)
				)
			)


def get_season_status(start_date, end_date, reference_date=None):
	"""Return the date-derived Season status using inclusive boundaries."""
	reference_date = getdate(reference_date or nowdate())
	start_date = getdate(start_date)
	end_date = getdate(end_date)

	if reference_date < start_date:
		return "Not Started"
	if reference_date > end_date:
		return "Ended"
	return "Ongoing"


def update_season_statuses():
	"""Refresh stored statuses for list views and mobile reference-data sync."""
	for season in frappe.get_all(
		"Season",
		fields=["name", "start_date", "end_date", "season_status"],
	):
		if not season.start_date or not season.end_date:
			continue
		status = get_season_status(season.start_date, season.end_date)
		if season.season_status != status:
			frappe.db.set_value("Season", season.name, "season_status", status, update_modified=False)


@frappe.whitelist()
def get_season_for_date(reference_date=None):
	"""Find the single Season containing a date; used by Desk and mobile clients."""
	reference_date = getdate(reference_date or nowdate())
	seasons = frappe.get_all(
		"Season",
		filters={
			"start_date": ["<=", reference_date],
			"end_date": [">=", reference_date],
		},
		fields=["name", "season_name", "season_status", "start_date", "end_date"],
		order_by="start_date desc",
		limit=2,
	)
	if len(seasons) > 1:
		frappe.throw(
			_("More than one Season covers {0}. Correct the overlapping Season dates.").format(
				frappe.format_value(reference_date, {"fieldtype": "Date"})
			)
		)
	return seasons[0] if seasons else None
