# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


UOM_ALIASES = {
	"%": "Percent",
	"acre": "Acre",
	"acres": "Acre",
	"bags": "Bag",
	"cm": "Centimeter",
	"grams": "Gram",
	"hectares": "Hectare",
	"kg": "Kg",
	"l": "Litre",
	"meters": "Meter",
	"ml": "Millilitre",
	"percent": "Percent",
	"person-days": "Person Day",
	"pieces": "Nos",
	"weeks": "Week",
}

FIELDOPS_UOMS = {
	"Acre": False,
	"Bag": True,
	"Centimeter": False,
	"Gram": False,
	"Hectare": False,
	"Kg": False,
	"Litre": False,
	"Meter": False,
	"Millilitre": False,
	"Nos": True,
	"Percent": False,
	"Person Day": False,
	"Week": False,
}


def normalize_uom(value):
	"""Return the canonical ERPNext UOM name for a FieldOps unit value."""
	if value is None:
		return None

	value = str(value).strip()
	if not value:
		return value

	return UOM_ALIASES.get(value.casefold(), value)


def ensure_fieldops_uoms(extra_values=None):
	"""Create or enable the ERPNext UOM records required by FieldOps."""
	uoms = dict(FIELDOPS_UOMS)
	for value in extra_values or []:
		if canonical := normalize_uom(value):
			uoms.setdefault(canonical, False)

	for uom_name, must_be_whole_number in uoms.items():
		if frappe.db.exists("UOM", uom_name):
			if not frappe.db.get_value("UOM", uom_name, "enabled"):
				frappe.db.set_value("UOM", uom_name, "enabled", 1, update_modified=False)
			continue

		frappe.get_doc(
			{
				"doctype": "UOM",
				"uom_name": uom_name,
				"enabled": 1,
				"must_be_whole_number": int(must_be_whole_number),
			}
		).insert(ignore_permissions=True)


def get_item_uom_conversion(item_code, uom=None):
	"""Resolve an operational UOM to an Item's stock UOM without guessing package sizes."""
	item = frappe.db.get_value(
		"Item",
		item_code,
		["stock_uom", "variant_of"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("Item {0} does not exist.").format(frappe.bold(item_code)))

	uom = normalize_uom(uom) or item.stock_uom
	if not frappe.db.exists("UOM", uom):
		frappe.throw(_("UOM {0} does not exist.").format(frappe.bold(uom)))
	if uom == item.stock_uom:
		return frappe._dict(
			{"uom": uom, "stock_uom": item.stock_uom, "conversion_factor": 1.0}
		)

	filters = {
		"parent": ["in", [item_code, item.variant_of] if item.variant_of else [item_code]],
		"parenttype": "Item",
		"uom": uom,
	}
	conversion_factor = frappe.db.get_value(
		"UOM Conversion Detail",
		filters,
		"conversion_factor",
		order_by="parent asc",
	)
	if flt(conversion_factor) <= 0:
		frappe.throw(
			_(
				"Item {0} has no conversion from {1} to its Stock UOM {2}. "
				"Add the conversion in the Item's UOM table."
			).format(
				frappe.bold(item_code),
				frappe.bold(uom),
				frappe.bold(item.stock_uom),
			)
		)
	return frappe._dict(
		{
			"uom": uom,
			"stock_uom": item.stock_uom,
			"conversion_factor": flt(conversion_factor),
		}
	)
