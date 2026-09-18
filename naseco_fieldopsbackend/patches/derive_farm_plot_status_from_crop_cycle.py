import frappe


def execute():
    """Farm Plot status is now derived from its Crop Cycle: Active only while
    a linked Crop Cycle is ACTIVE, Idle otherwise (including plots with no
    Crop Cycle, or one that is PLANNED/COMPLETED)."""
    active_plots = set(
        frappe.get_all(
            "Crop Cycle",
            filters={"status": "ACTIVE", "plot": ["is", "set"]},
            pluck="plot",
        )
    )

    all_plots = frappe.get_all("Farm Plot", pluck="name")
    for plot_name in all_plots:
        frappe.db.set_value(
            "Farm Plot",
            plot_name,
            "status",
            "Active" if plot_name in active_plots else "Idle",
            update_modified=False,
        )
