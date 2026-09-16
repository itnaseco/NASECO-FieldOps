from __future__ import annotations

import math

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate


HECTARES_PER_ACRE = 0.40468564224


def resolve_recipe(crop, variety=None, outgrower=None, company=None, on_date=None):
    """Return the most-specific active recipe: grower+variety, variety, then crop."""
    on_date = getdate(on_date or nowdate())
    rows = frappe.get_all(
        "Crop Recipe",
        filters={"crop": crop, "docstatus": 1, "status": "Active"},
        fields=["name", "variety", "outgrower", "company", "effective_from", "effective_to", "is_default"],
    )
    eligible = []
    for row in rows:
        if row.effective_from and getdate(row.effective_from) > on_date:
            continue
        if row.effective_to and getdate(row.effective_to) < on_date:
            continue
        if row.company and company and row.company != company:
            continue
        if row.variety and row.variety != variety:
            continue
        if row.outgrower and row.outgrower != outgrower:
            continue
        score = (4 if row.outgrower else 0) + (2 if row.variety else 0) + (1 if row.company else 0)
        eligible.append((score, int(row.is_default or 0), row.name))
    if not eligible:
        return None
    eligible.sort(reverse=True)
    return eligible[0][2]


def get_active_pricing_policy(company, on_date=None, policy=None):
    if policy:
        doc = frappe.get_doc("Input Recovery Pricing Policy", policy)
        if doc.docstatus != 1 or doc.status != "Active":
            frappe.throw(_("Input Recovery Pricing Policy {0} is not active.").format(policy))
        return doc
    on_date = getdate(on_date or nowdate())
    names = frappe.get_all(
        "Input Recovery Pricing Policy",
        filters={"company": company, "docstatus": 1, "status": "Active", "effective_from": ["<=", on_date]},
        pluck="name",
        order_by="effective_from desc, modified desc",
    )
    for name in names:
        doc = frappe.get_doc("Input Recovery Pricing Policy", name)
        if not doc.effective_to or getdate(doc.effective_to) >= on_date:
            return doc
    return None


def resolve_markup(policy, item_code, crop=None, variety=None, override=None):
    if isinstance(policy, str):
        policy = frappe.get_doc("Input Recovery Pricing Policy", policy)
    if override is not None:
        return flt(override)
    if not policy:
        return 0
    item_group = frappe.db.get_value("Item", item_code, "item_group")
    ranked = []
    for row in policy.exceptions or []:
        if row.item_code and row.item_code != item_code:
            continue
        if row.item_group and row.item_group != item_group:
            continue
        if row.crop and row.crop != crop:
            continue
        if row.variety and row.variety != variety:
            continue
        score = (8 if row.item_code else 0) + (4 if row.item_group else 0) + (2 if row.variety else 0) + (1 if row.crop else 0)
        ranked.append((score, flt(row.markup_percent)))
    return max(ranked)[1] if ranked else flt(policy.default_markup_percent)


def get_forecast_base_rate(item_code, warehouse=None):
    if warehouse:
        rate = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate")
        if flt(rate):
            return flt(rate)
    last_rate = frappe.db.sql(
        """
        select pri.base_rate
          from `tabPurchase Receipt Item` pri
          join `tabPurchase Receipt` pr on pr.name = pri.parent
         where pr.docstatus = 1 and pri.item_code = %s
         order by pr.posting_date desc, pr.posting_time desc
         limit 1
        """,
        item_code,
    )
    if last_rate and flt(last_rate[0][0]):
        return flt(last_rate[0][0])
    return flt(frappe.db.get_value("Item", item_code, "standard_rate"))


def round_rate(value, increment):
    increment = flt(increment)
    return math.ceil(flt(value) / increment) * increment if increment > 0 else flt(value)


def iter_recipe_inputs(recipe):
    for row in recipe.inputs or []:
        yield row, row.recipe_stage
    for stage in recipe.stages or []:
        for row in stage.get("inputs") or []:
            yield row, stage.stage_name
    for row in recipe.parent_seed_items or []:
        yield frappe._dict({
            "name": row.name, "resource_type": "Stock Item", "item_code": row.item_code,
            "quantity_per_hectare": row.quantity_per_hectare, "quantity_per_acre": 0,
            "unit": row.uom, "stock_uom": row.stock_uom, "conversion_factor": 1,
            "source_warehouse": row.source_warehouse, "recovery_policy": row.recovery_policy,
            "recoverable_percent": row.recoverable_percent, "recovery_pricing_policy": None,
            "markup_percent_override": None, "markup_override_reason": None,
        }), "Planting"


def build_crop_cycle_input_plan(cycle):
    if not cycle.recipe:
        return
    recipe = frappe.get_doc("Crop Recipe", cycle.recipe)
    area = flt(cycle.contracted_area_hectares) or flt(cycle.contracted_area_acres) * HECTARES_PER_ACRE
    policy = get_active_pricing_policy(cycle.company)
    stage_offsets = {row.stage_name: row.start_day_offset for row in recipe.stages or []}
    cycle.set("planned_inputs", [])
    total = 0
    for row, stage_name in iter_recipe_inputs(recipe):
        if row.resource_type != "Stock Item" or not row.item_code:
            continue
        per_ha = flt(row.quantity_per_hectare) or flt(row.quantity_per_acre) / HECTARES_PER_ACRE
        planned_qty = per_ha * area
        conversion = flt(row.conversion_factor) or 1
        base_rate = get_forecast_base_rate(row.item_code, row.source_warehouse)
        row_policy = get_active_pricing_policy(cycle.company, policy=row.recovery_pricing_policy) if row.recovery_pricing_policy else policy
        markup = resolve_markup(row_policy, row.item_code, cycle.crop, cycle.variety, row.markup_percent_override if row.markup_override_reason else None)
        rate = round_rate(base_rate * (1 + markup / 100), row_policy.rounding_increment if row_policy else 0)
        recoverable_percent = flt(row.recoverable_percent) if row.recovery_policy in ("Fully Recoverable", "Partially Recoverable") else 0
        amount = planned_qty * conversion * rate * recoverable_percent / 100
        required_by = add_days(cycle.planting_date or cycle.start_date, stage_offsets.get(stage_name, 0)) if (cycle.planting_date or cycle.start_date) else None
        cycle.append("planned_inputs", {
            "recipe_input_row": row.name,
            "stage_name": stage_name,
            "required_by": required_by,
            "item_code": row.item_code,
            "quantity_per_hectare": per_ha,
            "planned_qty": planned_qty,
            "uom": row.unit,
            "stock_uom": row.stock_uom,
            "planned_stock_qty": planned_qty * conversion,
            "source_warehouse": row.source_warehouse,
            "pricing_policy": row_policy.name if row_policy else None,
            "cost_basis": row_policy.cost_basis if row_policy else "Stock Valuation",
            "forecast_base_rate": base_rate,
            "markup_percent": markup,
            "forecast_recovery_rate": rate,
            "recoverable_percent": recoverable_percent,
            "forecast_recoverable_amount": amount,
        })
        total += amount
    cycle.forecast_input_recovery = total


@frappe.whitelist()
def create_stage_input_request_from_plan(crop_cycle, stage=None):
    cycle = frappe.get_doc("Crop Cycle", crop_cycle)
    if not cycle.planned_inputs:
        build_crop_cycle_input_plan(cycle)
    rows = [row for row in cycle.planned_inputs if not stage or row.stage_name == stage]
    if not rows:
        frappe.throw(_("No planned stock inputs are available for the selected stage."))
    request = frappe.new_doc("Stage Input Request")
    request.crop_cycle = cycle.name
    request.stage = frappe.db.get_value("Crop Cycle Stage", {"crop_cycle": cycle.name, "stage_name": stage}) if stage else None
    request.required_by = min((row.required_by for row in rows if row.required_by), default=nowdate())
    request.source_warehouse = next((row.source_warehouse for row in rows if row.source_warehouse), None)
    for row in rows:
        policy_version = frappe.db.get_value("Input Recovery Pricing Policy", row.pricing_policy, "policy_version") if row.pricing_policy else None
        request.append("items", {
            "recipe_input_item": row.recipe_input_row,
            "item_code": row.item_code,
            "requested_qty": row.planned_qty,
            "approved_qty": row.planned_qty,
            "uom": row.uom,
            "source_warehouse": row.source_warehouse,
            "estimated_rate": row.forecast_base_rate,
            "recovery_policy": "Fully Recoverable" if row.recoverable_percent == 100 else "Partially Recoverable",
            "recoverable_percent": row.recoverable_percent,
            "recovery_rate_basis": "Actual Purchase Cost + Markup",
            "recovery_pricing_policy": row.pricing_policy,
            "pricing_policy_version": policy_version,
            "markup_percent": row.markup_percent,
        })
    request.insert()
    return request.name


def provision_approved_stage_input_requests(crop_cycle):
    """Create and approve every recipe-backed stage input request atomically.

    The method is intentionally server-owned and idempotent.  Mobile clients only
    consume the resulting requests; they must never independently derive stock
    authorisations from cached recipe data.
    """
    cycle = (
        frappe.get_doc("Crop Cycle", crop_cycle)
        if isinstance(crop_cycle, str)
        else crop_cycle
    )
    if not cycle.planting_date_confirmed:
        return {"created": [], "existing": [], "stages": 0}

    # planned_inputs is the crop cycle's frozen recipe snapshot. Rebuilding it
    # after planting confirmation would silently change approved quantities when
    # the master recipe or valuation rates change.
    if not cycle.planned_inputs:
        build_crop_cycle_input_plan(cycle)
    _validate_automatic_input_approval(cycle)

    rows_by_stage = {}
    for row in cycle.planned_inputs or []:
        if flt(row.planned_qty) <= 0:
            continue
        rows_by_stage.setdefault(row.stage_name or "Planting", []).append(row)

    if not rows_by_stage:
        return {"created": [], "existing": [], "stages": 0}

    stage_names = frappe.get_all(
        "Crop Cycle Stage",
        filters={"crop_cycle": cycle.name},
        fields=["name", "stage_name"],
    )
    stages = {row.stage_name: row.name for row in stage_names}
    missing_stages = sorted(set(rows_by_stage) - set(stages))
    if missing_stages:
        frappe.throw(
            _("Crop-cycle stages are missing for recipe stages: {0}.").format(
                ", ".join(missing_stages)
            ),
            title=_("Input Request Provisioning Failed"),
        )

    default_warehouse = frappe.db.get_single_value(
        "FieldOps Settings", "default_source_warehouse"
    )
    problems = []
    for stage_name, rows in rows_by_stage.items():
        for row in rows:
            warehouse = row.source_warehouse or default_warehouse
            if not warehouse:
                problems.append(_("{0}: source warehouse is missing").format(stage_name))
            elif not frappe.db.exists("Warehouse", warehouse):
                problems.append(
                    _("{0}: warehouse {1} does not exist").format(stage_name, warehouse)
                )
            if not frappe.db.exists("Item", row.item_code):
                problems.append(
                    _("{0}: stock item {1} does not exist").format(
                        stage_name, row.item_code
                    )
                )
    if problems:
        frappe.throw(
            _("Automatic input approval cannot continue:<br>{0}").format(
                "<br>".join(sorted(set(problems)))
            ),
            title=_("Input Request Provisioning Failed"),
        )

    # Preflight existing records before creating anything. A non-approved manual
    # request is never silently promoted by automation.
    existing = []
    for stage_name, stage_id in stages.items():
        if stage_name not in rows_by_stage:
            continue
        current = frappe.db.get_value(
            "Stage Input Request",
            {"crop_cycle": cycle.name, "stage": stage_id, "docstatus": ["<", 2]},
            ["name", "docstatus", "status"],
            as_dict=True,
        )
        if current and current.docstatus != 1:
            frappe.throw(
                _(
                    "Stage {0} already has unapproved input request {1}. "
                    "Review or cancel it before provisioning."
                ).format(stage_name, frappe.bold(current.name)),
                title=_("Input Request Requires Review"),
            )
        if current:
            existing.append(current.name)

    created = []
    for stage_name, rows in rows_by_stage.items():
        stage_id = stages[stage_name]
        if frappe.db.exists(
            "Stage Input Request",
            {"crop_cycle": cycle.name, "stage": stage_id, "docstatus": 1},
        ):
            continue

        request = frappe.new_doc("Stage Input Request")
        request.flags.ignore_permissions = True
        request.request_id = f"AUTO-{cycle.name}-{stage_id}"[:140]
        request.crop_cycle = cycle.name
        request.stage = stage_id
        request.required_by = min(
            (row.required_by for row in rows if row.required_by), default=nowdate()
        )
        request.source_warehouse = next(
            (row.source_warehouse for row in rows if row.source_warehouse),
            default_warehouse,
        )
        request.notes = _(
            "Automatically generated and approved from Crop Recipe {0} when "
            "planting was confirmed for Crop Cycle {1}."
        ).format(cycle.recipe, cycle.name)
        for row in rows:
            policy_version = (
                frappe.db.get_value(
                    "Input Recovery Pricing Policy",
                    row.pricing_policy,
                    "policy_version",
                )
                if row.pricing_policy
                else None
            )
            request.append(
                "items",
                {
                    "recipe_input_item": row.recipe_input_row,
                    "item_code": row.item_code,
                    "requested_qty": row.planned_qty,
                    "approved_qty": row.planned_qty,
                    "uom": row.uom,
                    "source_warehouse": row.source_warehouse or default_warehouse,
                    "estimated_rate": row.forecast_base_rate,
                    "recovery_policy": (
                        "Fully Recoverable"
                        if flt(row.recoverable_percent) == 100
                        else "Partially Recoverable"
                    ),
                    "recoverable_percent": row.recoverable_percent,
                    "recovery_rate_basis": "Actual Purchase Cost + Markup",
                    "recovery_pricing_policy": row.pricing_policy,
                    "pricing_policy_version": policy_version,
                    "markup_percent": row.markup_percent,
                },
            )
        request.insert(ignore_permissions=True)
        request.submit()
        material_request_name = request.material_request or frappe.db.get_value(
            "Stage Input Request", request.name, "material_request"
        )
        if material_request_name:
            material_request = frappe.get_doc(
                "Material Request", material_request_name
            )
            if material_request.docstatus == 0:
                material_request.flags.ignore_permissions = True
                material_request.submit()
        created.append(request.name)

    return {
        "created": created,
        "existing": existing,
        "stages": len(rows_by_stage),
    }


def _validate_automatic_input_approval(cycle):
    if not cycle.recipe:
        frappe.throw(
            _("A submitted, active Crop Recipe is required before confirming planting."),
            title=_("Crop Recipe Required"),
        )
    recipe = frappe.get_doc("Crop Recipe", cycle.recipe)
    if recipe.docstatus != 1 or recipe.status != "Active":
        frappe.throw(
            _("Crop Recipe {0} must be submitted and Active.").format(
                frappe.bold(recipe.name)
            ),
            title=_("Crop Recipe Not Active"),
        )
    if not cycle.production_contract:
        frappe.throw(_("A submitted Production Contract is required."))
    contract = frappe.get_doc("Outgrower Production Contract", cycle.production_contract)
    if contract.docstatus != 1 or contract.status not in ("Active", "Fulfilled"):
        frappe.throw(
            _("Production Contract {0} must be submitted and Active.").format(
                frappe.bold(contract.name)
            )
        )
    area = flt(cycle.contracted_area_hectares) or (
        flt(cycle.contracted_area_acres) * HECTARES_PER_ACRE
    )
    if area <= 0:
        frappe.throw(
            _("Contracted Area (hectares) must be greater than zero."),
            title=_("Invalid Contracted Area"),
        )

    recovery = flt(cycle.forecast_input_recovery)
    harvest_value = flt(cycle.expected_harvest_value)
    exposure_percent = flt(cycle.max_exposure_percent)
    if recovery > 0 and harvest_value > 0 and exposure_percent > 0:
        limit = harvest_value * exposure_percent / 100
        if recovery > limit:
            frappe.throw(
                _(
                    "Forecast recoverable inputs ({0}) exceed the contract exposure "
                    "limit ({1})."
                ).format(
                    frappe.format_value(recovery, {"fieldtype": "Currency"}),
                    frappe.format_value(limit, {"fieldtype": "Currency"}),
                ),
                title=_("Exposure Limit Exceeded"),
            )


@frappe.whitelist()
def preview_recipe_demand(recipe, area_hectares, planting_date=None):
    """Preview calculated quantities and risk-adjusted exposure without creating transactions."""
    source = frappe.get_doc("Crop Recipe", recipe)
    cycle = frappe.new_doc("Crop Cycle")
    cycle.recipe = source.name
    cycle.crop = source.crop
    cycle.variety = source.variety
    cycle.company = source.company
    cycle.contracted_area_hectares = flt(area_hectares)
    cycle.planting_date = planting_date or nowdate()
    build_crop_cycle_input_plan(cycle)
    return {
        "recipe": source.name,
        "area_hectares": flt(area_hectares),
        "forecast_input_recovery": cycle.forecast_input_recovery,
        "items": [row.as_dict() for row in cycle.planned_inputs],
    }
