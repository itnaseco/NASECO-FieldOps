import frappe

from naseco_fieldopsbackend.crop_cycle_lifecycle import LIFECYCLE_STAGES


def execute():
    # Metadata for upgraded sites; changing the original patch alone would not
    # update the already-created custom child DocType.
    if frappe.db.exists("DocType", "Inspection Template Applicability"):
        field = frappe.db.get_value("DocField", {"parent": "Inspection Template Applicability", "fieldname": "variety"}, "name")
        if field:
            frappe.db.set_value("DocField", field, "options", "Crop Variety", update_modified=False)
            frappe.clear_cache(doctype="Inspection Template Applicability")
    if not frappe.db.exists("DocType", "Stage Definition"):
        return
    for stage in LIFECYCLE_STAGES:
        if not frappe.db.exists("Stage Definition", stage.code):
            frappe.get_doc({"doctype": "Stage Definition", "stage_code": stage.code,
                "stage_name": stage.name, "active": 1}).insert(ignore_permissions=True)
    if frappe.db.has_column("Recipe Stage", "stage_definition"):
        for stage in LIFECYCLE_STAGES:
            frappe.db.sql("""update `tabRecipe Stage` set stage_definition=%s
                where stage_code=%s and ifnull(stage_definition, '')=''""", (stage.code, stage.code))
    frappe.clear_cache()
