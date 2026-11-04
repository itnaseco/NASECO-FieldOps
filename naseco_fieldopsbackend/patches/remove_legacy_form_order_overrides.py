"""Remove obsolete form-order overrides that mask source-controlled layouts."""

import json

import frappe


LEGACY_ORDERS = {
    "Outgrower": ("outgrower_id", "ux_overview_tab"),
    "Crop Cycle": ("section_break_1", "ux_overview_tab"),
    "Farm Plot": ("plot_id", "ux_overview_tab"),
    "Seed Variety Parentage": ("output_variety", "form_layout_0_section_break"),
    "Inspection": ("inspection_id", "ux_overview_tab"),
    "Outgrower Production Contract": ("outgrower", "ux_overview_tab"),
    "Parent Seed Lot Analysis": ("parent_variety", "form_layout_0_tab_break"),
}


def execute():
    for doctype, (legacy_first, current_first) in LEGACY_ORDERS.items():
        setter_name = f"{doctype}-main-field_order"
        value = frappe.db.get_value("Property Setter", setter_name, "value")
        if not value:
            continue
        try:
            order = json.loads(value)
        except (TypeError, ValueError):
            continue
        if order and order[0] == legacy_first and current_first not in order:
            frappe.delete_doc("Property Setter", setter_name, ignore_permissions=True)
