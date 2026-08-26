# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe

from naseco_fieldopsbackend.roles import OUTGROWER_MANAGER_ROLE


PLANNING_MASTERS = (
    "Season",
    "Region",
    "Location",
    "Crop",
    "Crop Variety",
)
ROLE_ACCESS = {
    OUTGROWER_MANAGER_ROLE: {"delete": 0},
    "Administrator": {"delete": 1},
}


def execute():
    """Expose planning-master maintenance actions to the authorized Desk roles."""
    for doctype in PLANNING_MASTERS:
        if not frappe.db.exists("DocType", doctype):
            continue

        for role, access in ROLE_ACCESS.items():
            filters = {"parent": doctype, "role": role, "permlevel": 0}
            name = frappe.db.exists("Custom DocPerm", filters)
            permission = (
                frappe.get_doc("Custom DocPerm", name)
                if name
                else frappe.new_doc("Custom DocPerm")
            )
            permission.update(
                {
                    **filters,
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "delete": access["delete"],
                    "report": 1,
                    "print": 1,
                    "email": 1,
                }
            )
            permission.save(ignore_permissions=True)

    frappe.clear_cache()
