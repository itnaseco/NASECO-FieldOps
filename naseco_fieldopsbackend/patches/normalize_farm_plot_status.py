import frappe


def execute():
    """Collapse the legacy ACTIVE/IDLE Farm Plot status values into Active/Idle."""
    frappe.db.sql(
        """
        update `tabFarm Plot`
        set status = 'Active'
        where status = 'ACTIVE'
        """
    )
    frappe.db.sql(
        """
        update `tabFarm Plot`
        set status = 'Idle'
        where status = 'IDLE'
        """
    )
