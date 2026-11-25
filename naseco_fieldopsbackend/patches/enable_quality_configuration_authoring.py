import frappe


def execute():
    # Existing sites have Custom DocPerm rows that override the source DocPerms.
    grants = {
        ("Inspection Template", "Quality Manager"): (1, 1, 1, 0),
        ("Inspection Parameter", "Quality Manager"): (1, 1, 1, 0),
        ("Inspection Attribute", "Quality Manager"): (1, 1, 1, 0),
        ("Inspection Standard", "Quality Manager"): (1, 0, 0, 0),
        ("Stage Definition", "Outgrower Manager"): (1, 1, 1, 1),
    }
    for (doctype, role), (read, write, create, delete) in grants.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        filters = {"parent": doctype, "role": role, "permlevel": 0}
        name = frappe.db.exists("Custom DocPerm", filters)
        row = frappe.get_doc("Custom DocPerm", name) if name else frappe.new_doc("Custom DocPerm")
        row.update({**filters, "read": read, "write": write, "create": create,
                    "delete": delete, "report": read, "print": read, "email": read})
        row.save(ignore_permissions=True)
        frappe.clear_cache(doctype=doctype)
    field = frappe.db.get_value("Custom Field", {"dt": "Inspection Template", "fieldname": "lifecycle_status"}, "name")
    if field:
        frappe.db.set_value("Custom Field", field, "default", "Draft", update_modified=False)
        frappe.clear_cache(doctype="Inspection Template")
