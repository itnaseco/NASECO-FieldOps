import frappe
from frappe import _

from naseco_fieldopsbackend.fieldops_finance import calculate_crop_cycle_exposure


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	cycle_filters = {}
	if filters.company:
		cycle_filters["company"] = filters.company
	if filters.status:
		cycle_filters["status"] = filters.status

	cycles = frappe.get_all(
		"Crop Cycle",
		filters=cycle_filters,
		fields=[
			"name",
			"plot",
			"crop",
			"supplier",
			"currency",
			"expected_harvest_value",
			"status",
		],
		order_by="modified desc",
	)
	data = []
	for cycle in cycles:
		exposure = calculate_crop_cycle_exposure(cycle.name)
		data.append(
			{
				"crop_cycle": cycle.name,
				"plot": cycle.plot,
				"crop": cycle.crop,
				"supplier": cycle.supplier,
				"status": cycle.status,
				"expected_harvest_value": exposure.expected_harvest_value,
				"risk_adjusted_harvest_value": exposure.risk_adjusted_harvest_value,
				"exposure_limit": exposure.exposure_limit,
				"recoverable_stock_value": exposure.recoverable_stock_value,
				"cash_advanced": exposure.cash_advanced,
				"pending_cash_advance": exposure.pending_cash_advance,
				"committed_exposure": exposure.committed_exposure,
				"available_capacity": exposure.available_advance_capacity,
				"actual_harvest_value": exposure.actual_harvest_value,
				"actual_net_position": exposure.actual_net_position,
				"currency": cycle.currency,
			}
		)
	return columns, data


def get_columns():
	return [
		{"fieldname": "crop_cycle", "label": _("Crop Cycle"), "fieldtype": "Link", "options": "Crop Cycle", "width": 180},
		{"fieldname": "plot", "label": _("Farm Plot"), "fieldtype": "Link", "options": "Farm Plot", "width": 150},
		{"fieldname": "crop", "label": _("Crop"), "fieldtype": "Link", "options": "Crop", "width": 100},
		{"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier", "width": 180},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 90},
		{"fieldname": "expected_harvest_value", "label": _("Expected Harvest"), "fieldtype": "Currency", "options": "currency", "width": 140},
		{"fieldname": "risk_adjusted_harvest_value", "label": _("Risk-adjusted Harvest"), "fieldtype": "Currency", "options": "currency", "width": 150},
		{"fieldname": "exposure_limit", "label": _("Exposure Limit"), "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "recoverable_stock_value", "label": _("Stock Inputs"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "cash_advanced", "label": _("Cash Advanced"), "fieldtype": "Currency", "options": "currency", "width": 125},
		{"fieldname": "pending_cash_advance", "label": _("Pending Advances"), "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "committed_exposure", "label": _("Committed Exposure"), "fieldtype": "Currency", "options": "currency", "width": 145},
		{"fieldname": "available_capacity", "label": _("Available Capacity"), "fieldtype": "Currency", "options": "currency", "width": 140},
		{"fieldname": "actual_harvest_value", "label": _("Actual Harvest"), "fieldtype": "Currency", "options": "currency", "width": 125},
		{"fieldname": "actual_net_position", "label": _("Net Position"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]
