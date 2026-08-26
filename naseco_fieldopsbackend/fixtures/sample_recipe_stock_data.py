"""Additive demonstration data for recipe, risk pricing, input planning, and reject warehouses.

Run explicitly with:
bench --site <site> execute naseco_fieldopsbackend.fixtures.sample_recipe_stock_data.execute
"""

import frappe

from naseco_fieldopsbackend.crop_cycle_lifecycle import LIFECYCLE_STAGES
from naseco_fieldopsbackend.fieldops_finance import ensure_finance_reference_data, get_default_company


SAMPLE_ITEMS = {
    "FO-MAIZE-FEMALE-PARENT": ("Maize Female Parent Seed", "Kg", 24000),
    "FO-MAIZE-MALE-PARENT": ("Maize Male Parent Seed", "Kg", 22000),
    "FO-RICE-CERTIFIED-SEED": ("Rice Certified Seed", "Kg", 8500),
    "FO-SOYBEAN-BASIC-SEED": ("Soybean Basic Seed", "Kg", 9000),
    "FO-NPK-17-17-17": ("NPK 17-17-17 Fertilizer", "Kg", 4200),
    "FO-SEED-DRESSING": ("Seed Dressing Chemical", "Litre", 38000),
}


def execute():
    ensure_finance_reference_data()
    company = get_default_company()
    if not company:
        frappe.throw("A Company is required before loading FieldOps recipe samples.")
    ensure_items()
    warehouses = ensure_warehouses(company)
    configure_settings(warehouses)
    policy = ensure_pricing_policy(company)
    ensure_recipes(company, policy, warehouses["Stores"])
    frappe.db.commit()
    return {
        "pricing_policy": policy,
        "warehouses": warehouses,
        "recipes": frappe.get_all("Crop Recipe", filters={"recipe_id": ["like", "SAMPLE-%"]}, pluck="name"),
    }


def ensure_items():
    group = "Agricultural Inputs"
    for code, (name, uom, rate) in SAMPLE_ITEMS.items():
        if frappe.db.exists("Item", code):
            continue
        frappe.get_doc({
            "doctype": "Item", "item_code": code, "item_name": name,
            "item_group": group, "stock_uom": uom, "is_stock_item": 1,
            "is_purchase_item": 1, "is_sales_item": 0, "has_batch_no": 1,
            "create_new_batch": 1, "standard_rate": rate,
        }).insert(ignore_permissions=True)


def ensure_warehouses(company):
    abbreviation = frappe.db.get_value("Company", company, "abbr")
    result = {}
    for key, label in {
        "Stores": "FieldOps Input Stores", "Quarantine": "Harvest Quarantine",
        "Seed": "Accepted Seed", "Grain": "Grain Downgrade", "Reject": "Harvest Rejects",
    }.items():
        existing = frappe.db.get_value("Warehouse", {"company": company, "warehouse_name": label})
        if not existing:
            existing = frappe.get_doc({
                "doctype": "Warehouse", "warehouse_name": label,
                "company": company, "is_group": 0,
            }).insert(ignore_permissions=True).name
        result[key] = existing or f"{label} - {abbreviation}"
    return result


def configure_settings(warehouses):
    settings = frappe.get_single("FieldOps Settings")
    mapping = {
        "default_source_warehouse": warehouses["Stores"],
        "harvest_quarantine_warehouse": warehouses["Quarantine"],
        "accepted_seed_warehouse": warehouses["Seed"],
        "grain_warehouse": warehouses["Grain"],
        "reject_warehouse": warehouses["Reject"],
    }
    for fieldname, value in mapping.items():
        if settings.meta.has_field(fieldname) and not settings.get(fieldname):
            settings.set(fieldname, value)
    settings.save(ignore_permissions=True)


def ensure_pricing_policy(company):
    name = "IRPP-SAMPLE-2026.1"
    existing = frappe.db.get_value("Input Recovery Pricing Policy", {"company": company, "policy_version": "SAMPLE-2026.1"})
    if existing:
        return existing
    doc = frappe.get_doc({
        "doctype": "Input Recovery Pricing Policy", "company": company,
        "policy_version": "SAMPLE-2026.1", "effective_from": "2026-01-01",
        "default_markup_percent": 12, "cost_basis": "Purchase Receipt Landed Rate",
        "rounding_increment": 10, "approval_threshold_percent": 20,
        "change_reason": "Demonstration policy for crop-cycle input risk recovery.",
        "exceptions": [
            {"item_group": "Agricultural Inputs", "crop": "Maize", "markup_percent": 15},
            {"item_code": "FO-MAIZE-FEMALE-PARENT", "markup_percent": 8},
            {"item_code": "FO-MAIZE-MALE-PARENT", "markup_percent": 8},
        ],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc.name


def stage_rows(overrides=None):
    overrides = overrides or {}
    return [{
        "stage_code": stage.code, "stage_name": stage.name, "order_index": stage.order,
        "start_day_offset": overrides.get(stage.code, (stage.start_day, stage.end_day))[0],
        "end_day_offset": overrides.get(stage.code, (stage.start_day, stage.end_day))[1],
    } for stage in LIFECYCLE_STAGES]


def input_row(item, per_ha, stage, uom="Kg", recovery=100, policy=None, warehouse=None):
    return {
        "resource_type": "Stock Item", "item_code": item, "quantity_per_hectare": per_ha,
        "unit": uom, "recipe_stage": stage, "recovery_policy": "Fully Recoverable" if recovery == 100 else "Partially Recoverable",
        "recoverable_percent": recovery, "recovery_rate_basis": "Actual Purchase Cost + Markup",
        "recovery_pricing_policy": policy, "source_warehouse": warehouse,
    }


def ensure_recipes(company, policy, warehouse):
    definitions = [
        {
            "name": "Sample Maize Base Recipe v1", "id": "SAMPLE-MAIZE-BASE-V1", "crop": "Maize", "variety": None,
            "overrides": {},
            "inputs": [
                input_row("FO-DAP-FERTILIZER", 125, "Planting", policy=policy, warehouse=warehouse),
                input_row("FO-UREA-FERTILIZER", 150, "Vegetative", policy=policy, warehouse=warehouse),
                input_row("FO-SEED-DRESSING", 0.6, "Planting", "Litre", 75, policy, warehouse),
                input_row("FO-LAMBDA-CYHALOTHRIN", 1.2, "Vegetative", "Litre", 100, policy, warehouse),
            ],
            "parents": [],
        },
        {
            "name": "Sample Longe 10H Hybrid Recipe v1", "id": "SAMPLE-MAIZE-L10H-V1", "crop": "Maize", "variety": "Longe 10H",
            "overrides": {"EMERGENCE": (6, 12), "VEGETATIVE": (20, 42), "FLOWERING": (55, 70), "HARVEST": (115, 135), "DELIVERY": (136, 145)},
            "inputs": [
                input_row("FO-DAP-FERTILIZER", 150, "Planting", policy=policy, warehouse=warehouse),
                input_row("FO-UREA-FERTILIZER", 175, "Vegetative", policy=policy, warehouse=warehouse),
                input_row("FO-NPK-17-17-17", 80, "Pre-flowering", policy=policy, warehouse=warehouse),
                input_row("FO-SEED-DRESSING", 0.75, "Planting", "Litre", 75, policy, warehouse),
            ],
            "parents": [
                {"parent_role":"Female","ratio_group":"Hybrid 4:1","ratio_value":4,"item_code":"FO-MAIZE-FEMALE-PARENT","quantity_per_hectare":20,"uom":"Kg","recovery_policy":"Fully Recoverable","recoverable_percent":100,"source_warehouse":warehouse},
                {"parent_role":"Male","ratio_group":"Hybrid 4:1","ratio_value":1,"item_code":"FO-MAIZE-MALE-PARENT","quantity_per_hectare":5,"uom":"Kg","recovery_policy":"Fully Recoverable","recoverable_percent":100,"source_warehouse":warehouse},
            ],
        },
        {
            "name": "Sample WITA 9 Rice Recipe v1", "id": "SAMPLE-RICE-WITA9-V1", "crop": "Rice", "variety": "WITA 9",
            "overrides": {"PLANTING": (0, 4), "EMERGENCE": (8, 18), "VEGETATIVE": (19, 55), "HARVEST": (118, 132), "DELIVERY": (133, 145)},
            "inputs": [
                input_row("FO-RICE-CERTIFIED-SEED", 60, "Planting", policy=policy, warehouse=warehouse),
                input_row("FO-DAP-FERTILIZER", 100, "Planting", policy=policy, warehouse=warehouse),
                input_row("FO-UREA-FERTILIZER", 120, "Vegetative", policy=policy, warehouse=warehouse),
            ], "parents": [],
        },
        {
            "name": "Sample Maksoy 3N Soybean Recipe v1", "id": "SAMPLE-SOY-MAKSOY3N-V1", "crop": "Soybean", "variety": "Maksoy 3N",
            "overrides": {"EMERGENCE": (5, 10), "FLOWERING": (38, 55), "HARVEST": (92, 108), "DELIVERY": (109, 118)},
            "inputs": [
                input_row("FO-SOYBEAN-BASIC-SEED", 70, "Planting", policy=policy, warehouse=warehouse),
                input_row("FO-DAP-FERTILIZER", 80, "Planting", policy=policy, warehouse=warehouse),
                input_row("FO-MANCOZEB", 2.5, "Vegetative", policy=policy, warehouse=warehouse),
            ], "parents": [],
        },
    ]
    sample_grower = frappe.db.get_value("Outgrower", {}, "name", order_by="creation asc")
    if sample_grower:
        definitions.append({
            "name": "Sample Longe 10H Grower Override v1", "id": "SAMPLE-MAIZE-L10H-GROWER-V1",
            "crop": "Maize", "variety": "Longe 10H", "outgrower": sample_grower,
            "overrides": {"VEGETATIVE": (18, 40), "FLOWERING": (52, 68), "HARVEST": (112, 132), "DELIVERY": (133, 142)},
            "inputs": [
                input_row("FO-DAP-FERTILIZER", 165, "Planting", policy=policy, warehouse=warehouse),
                input_row("FO-UREA-FERTILIZER", 185, "Vegetative", policy=policy, warehouse=warehouse),
                input_row("FO-NPK-17-17-17", 90, "Pre-flowering", policy=policy, warehouse=warehouse),
            ],
            "parents": [
                {"parent_role":"Female","ratio_group":"Hybrid 4:1","ratio_value":4,"item_code":"FO-MAIZE-FEMALE-PARENT","quantity_per_hectare":21,"uom":"Kg","recovery_policy":"Fully Recoverable","recoverable_percent":100,"source_warehouse":warehouse},
                {"parent_role":"Male","ratio_group":"Hybrid 4:1","ratio_value":1,"item_code":"FO-MAIZE-MALE-PARENT","quantity_per_hectare":5.25,"uom":"Kg","recovery_policy":"Fully Recoverable","recoverable_percent":100,"source_warehouse":warehouse},
            ],
        })
    for data in definitions:
        if frappe.db.exists("Crop Recipe", data["name"]):
            continue
        recipe = frappe.get_doc({
            "doctype": "Crop Recipe", "recipe_name": data["name"], "recipe_id": data["id"],
            "crop": data["crop"], "variety": data["variety"], "company": company,
            "outgrower": data.get("outgrower"),
            "recipe_version": "1.0", "effective_from": "2026-01-01", "is_default": 1,
            "stages": stage_rows(data["overrides"]), "inputs": data["inputs"],
            "parent_seed_items": data["parents"],
        })
        recipe.insert(ignore_permissions=True)
        recipe.submit()
