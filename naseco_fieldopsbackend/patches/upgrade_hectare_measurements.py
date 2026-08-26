import frappe


ACRES_TO_HECTARES = 0.40468564224
PER_ACRE_TO_PER_HECTARE = 2.47105381467


def execute():
    """Backfill additive hectare fields without changing submitted history."""
    if frappe.db.has_column("Farm Plot", "area_hectares"):
        frappe.db.sql("""
            update `tabFarm Plot`
            set area_hectares = area_acres * %s
            where coalesce(area_hectares, 0) = 0 and coalesce(area_acres, 0) > 0
        """, ACRES_TO_HECTARES)

    if frappe.db.has_column("Season Production Target", "target_hectares"):
        frappe.db.sql("""
            update `tabSeason Production Target`
            set target_hectares = target_acres * %s,
                planned_yield_kg_per_hectare = planned_yield_kg_per_acre * %s,
                parent_seed_rate_per_hectare = parent_seed_rate_per_acre * %s
            where coalesce(target_hectares, 0) = 0
              and coalesce(target_acres, 0) > 0
        """, (ACRES_TO_HECTARES, PER_ACRE_TO_PER_HECTARE, PER_ACRE_TO_PER_HECTARE))

    if frappe.db.has_column("Season Production Plan", "target_hectares"):
        frappe.db.sql("""
            update `tabSeason Production Plan`
            set target_hectares = target_acres * %s
            where coalesce(target_hectares, 0) = 0 and coalesce(target_acres, 0) > 0
        """, ACRES_TO_HECTARES)

    if frappe.db.has_column("Outgrower Production Contract", "contracted_area_hectares"):
        frappe.db.sql("""
            update `tabOutgrower Production Contract`
            set contracted_area_hectares = contracted_area_acres * %s,
                quota_kg_per_hectare = quota_kg_per_acre * %s
            where docstatus = 0
              and (coalesce(contracted_area_hectares, 0) = 0
                   or coalesce(quota_kg_per_hectare, 0) = 0)
        """, (ACRES_TO_HECTARES, PER_ACRE_TO_PER_HECTARE))

    for code, label in (("ISOLATION_DISTANCE", "Isolation distance"), ("TIME_ISOLATION", "Time isolation")):
        parameter = frappe.db.get_value("Inspection Parameter", {"parameter_code": code})
        if parameter:
            frappe.db.set_value("Inspection Parameter", parameter, {"data_type": "Select", "unit": None}, update_modified=False)
            frappe.db.sql("""
                update `tabInspection Standard`
                set comparison_rule = %s, aggregation_method = %s,
                    expected_text = %s, minimum_value = 0, maximum_value = 0
                where parameter = %s
            """, ("Equals", "All Must Pass", "Adequate", label))

    frappe.db.sql("""
        update `tabAgronomy Report Parameter`
        set parameter_label = %s
        where parameter_code = %s
    """, ("Replanting Needed?", "GAP_FILLING"))
    frappe.db.sql("""
        update `tabAgronomy Report Result`
        set parameter_label = %s
        where parameter_code = %s and parenttype = %s
          and parent in (select name from `tabAgronomy Report` where docstatus = 0)
    """, ("Replanting Needed?", "GAP_FILLING", "Agronomy Report"))
