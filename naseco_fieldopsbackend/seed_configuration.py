import frappe
from frappe import _


def validate_seed_scope(seed_category, seed_class, context=None):
    """Validate that enabled seed category/class masters form a valid scope."""
    if not seed_category:
        return
    if not frappe.db.get_value("Seed Category", seed_category, "enabled"):
        frappe.throw(_("Seed Category {0} must be enabled.").format(frappe.bold(seed_category)))
    if not seed_class:
        return
    values = frappe.db.get_value(
        "Seed Class", seed_class, ["enabled"], as_dict=True
    )
    if not values or not values.enabled:
        frappe.throw(_("Seed Class {0} must be enabled.").format(frappe.bold(seed_class)))


def get_variety_seed_item(variety, seed_category, seed_class, item_purpose):
    """Return the configured default stock Item for a variety seed scope."""
    if not all((variety, seed_category, seed_class, item_purpose)):
        return None
    filters = {
        "parent": variety,
        "parenttype": "Crop Variety",
        "seed_category": seed_category,
        "seed_class": seed_class,
        "item_purpose": item_purpose,
    }
    return (
        frappe.db.get_value("Crop Variety Seed Item", {**filters, "is_default": 1}, "item_code")
        or frappe.db.get_value("Crop Variety Seed Item", filters, "item_code")
    )
