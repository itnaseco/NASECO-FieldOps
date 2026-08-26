import frappe
from frappe.utils import flt


def execute():
	"""Copy legacy contract parent-seed rows into the consolidated child table."""
	if not frappe.db.table_exists("tabContract Parent Seed Item"):
		return

	contracts = frappe.get_all(
		"Outgrower Production Contract",
		fields=[
			"name",
			"contracted_area_hectares",
			"parent_seed_item",
			"parent_seed_uom",
			"planned_parent_seed_qty",
			"parent_seed_rate",
		],
	)
	legacy_table_exists = frappe.db.table_exists("tabProduction Contract Parent Seed")

	for contract in contracts:
		if frappe.db.exists(
			"Contract Parent Seed Item",
			{"parent": contract.name, "parentfield": "parent_seed_items"},
		):
			continue

		legacy_rows = []
		if legacy_table_exists:
			legacy_rows = frappe.get_all(
				"Production Contract Parent Seed",
				filters={"parent": contract.name, "parentfield": "parent_seeds"},
				fields=[
					"parent_role",
					"parent_seed_item",
					"quantity_per_hectare",
					"uom",
					"planned_quantity",
					"rate",
					"planned_value",
				],
				order_by="idx asc",
			)

		if not legacy_rows and contract.parent_seed_item:
			area = flt(contract.contracted_area_hectares)
			quantity = flt(contract.planned_parent_seed_qty)
			legacy_rows = [
				frappe._dict(
					parent_role="Other",
					parent_seed_item=contract.parent_seed_item,
					quantity_per_hectare=quantity / area if area else 0,
					uom=contract.parent_seed_uom,
					planned_quantity=quantity,
					rate=contract.parent_seed_rate,
					planned_value=quantity * flt(contract.parent_seed_rate),
				)
			]

		for index, row in enumerate(legacy_rows, start=1):
			frappe.get_doc(
				{
					"doctype": "Contract Parent Seed Item",
					"parent": contract.name,
					"parenttype": "Outgrower Production Contract",
					"parentfield": "parent_seed_items",
					"idx": index,
					"parent_role": row.parent_role or "Other",
					"item": row.parent_seed_item,
					"uom": row.uom,
					"quantity_kg_per_hectare": row.quantity_per_hectare,
					"planned_quantity": row.planned_quantity,
					"rate": row.rate,
					"amount": row.planned_value,
				}
			).db_insert()
