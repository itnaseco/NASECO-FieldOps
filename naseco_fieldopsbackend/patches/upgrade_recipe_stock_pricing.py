import frappe

from naseco_fieldopsbackend.fieldops_finance import ensure_erpnext_custom_fields


HECTARES_PER_ACRE = 0.40468564224


def execute():
    ensure_erpnext_custom_fields()
    if frappe.db.exists("DocType", "Recipe Input Item"):
        frappe.db.sql(
            """update `tabRecipe Input Item`
                  set quantity_per_hectare = quantity_per_acre / %s,
                      stock_quantity_per_hectare = stock_quantity_per_acre / %s
                where coalesce(quantity_per_hectare, 0) = 0
                  and coalesce(quantity_per_acre, 0) > 0""",
            (HECTARES_PER_ACRE, HECTARES_PER_ACRE),
        )
    if frappe.db.exists("DocType", "Crop Recipe"):
        frappe.db.sql(
            """update `tabCrop Recipe`
                  set recipe_version = coalesce(nullif(recipe_version, ''), 'Legacy-1.0'),
                      status = case when docstatus = 1 then 'Active' else 'Draft' end,
                      effective_from = coalesce(effective_from, date(creation))"""
        )
