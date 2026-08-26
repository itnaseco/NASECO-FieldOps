import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = [
        {"label": _("Season"), "fieldname": "season", "fieldtype": "Link", "options": "Season", "width": 120},
        {"label": _("Crop"), "fieldname": "crop", "fieldtype": "Link", "options": "Crop", "width": 110},
        {"label": _("Variety"), "fieldname": "variety", "fieldtype": "Link", "options": "Crop Variety", "width": 130},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180},
        {"label": _("Warehouse"), "fieldname": "source_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
        {"label": _("Required Stock Qty"), "fieldname": "required_qty", "fieldtype": "Float", "width": 130},
        {"label": _("Available Qty"), "fieldname": "available_qty", "fieldtype": "Float", "width": 110},
        {"label": _("Procurement Shortage"), "fieldname": "shortage_qty", "fieldtype": "Float", "width": 140},
        {"label": _("Forecast Recovery"), "fieldname": "forecast_recovery", "fieldtype": "Currency", "width": 140},
    ]
    conditions = ["cycle.docstatus < 2"]
    values = {}
    for fieldname in ("season", "crop", "variety"):
        if filters.get(fieldname):
            conditions.append(f"cycle.{fieldname} = %({fieldname})s")
            values[fieldname] = filters[fieldname]
    rows = frappe.db.sql(
        f"""
        select cycle.season, cycle.crop, cycle.variety, plan.item_code, plan.source_warehouse,
               sum(plan.planned_stock_qty) required_qty,
               sum(plan.forecast_recoverable_amount) forecast_recovery
          from `tabCrop Cycle Planned Input` plan
          join `tabCrop Cycle` cycle on cycle.name = plan.parent
         where {' and '.join(conditions)}
         group by cycle.season, cycle.crop, cycle.variety, plan.item_code, plan.source_warehouse
         order by cycle.season, cycle.crop, cycle.variety, plan.item_code
        """,
        values,
        as_dict=True,
    )
    for row in rows:
        row.available_qty = flt(frappe.db.get_value("Bin", {"item_code": row.item_code, "warehouse": row.source_warehouse}, "projected_qty")) if row.source_warehouse else 0
        row.shortage_qty = max(flt(row.required_qty) - flt(row.available_qty), 0)
    return columns, rows
