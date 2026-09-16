import frappe

from naseco_fieldopsbackend.recipe_planning import (
    provision_approved_stage_input_requests,
)


def execute():
    """Provision confirmed cycles backed by explicitly versioned legacy recipes."""
    cycles = frappe.get_all(
        "Crop Cycle",
        filters={
            "planting_date_confirmed": 1,
            "status": ["in", ["PLANNED", "ACTIVE"]],
        },
        pluck="name",
        order_by="creation asc",
    )
    for index, cycle_name in enumerate(cycles):
        savepoint = f"reconcile_cycle_inputs_v3_{index}"
        frappe.db.savepoint(savepoint)
        try:
            provision_approved_stage_input_requests(cycle_name)
        except Exception:
            frappe.db.rollback(save_point=savepoint)
            frappe.log_error(
                title=f"Input reconciliation v3 failed for {cycle_name}",
                message=frappe.get_traceback(),
            )
