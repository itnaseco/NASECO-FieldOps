import frappe


def execute():
    name = frappe.db.exists("Custom DocPerm", {"parent": "Agronomy Report Template", "role": "Outgrower Manager", "permlevel": 0})
    if name:
        frappe.db.set_value("Custom DocPerm", name, {"read": 1, "create": 1, "write": 1}, update_modified=False)
    frappe.clear_cache(doctype="Agronomy Report Template")
