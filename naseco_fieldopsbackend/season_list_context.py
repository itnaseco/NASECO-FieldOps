"""Permission-aware navigation defaults. Never used to authorize business work."""

import frappe
from frappe.utils import nowdate


@frappe.whitelist()
def get_active_seasons():
	"""Only expose ongoing seasons with a readable, submitted Active plan."""
	if not all(frappe.has_permission(dt, "read") for dt in ("Season", "Season Production Plan")):
		return []
	today = nowdate()
	seasons = frappe.get_list(
		"Season", filters={"start_date": ["<=", today], "end_date": [">=", today]},
		fields=["name", "season_name"], order_by="start_date desc", limit_page_length=0,
	)
	if not seasons:
		return []
	plans = frappe.get_list(
		"Season Production Plan",
		filters={"season": ["in", [s.name for s in seasons]], "docstatus": 1, "status": "Active"},
		fields=["season"], limit_page_length=0,
	)
	active = {p.season for p in plans}
	return [s for s in seasons if s.name in active]


