import frappe
from frappe.utils import flt


ACRE_TO_HECTARE = 0.40468564224
PER_ACRE_TO_PER_HECTARE = 2.47105381467


AREA_FIELDS = {
	"Farm Plot": [("area_acres", "area_hectares")],
	"Crop Cycle": [("contracted_area_acres", "contracted_area_hectares")],
	"Crop Production Lot": [
		("area_acres", "area_hectares"),
		("accepted_area_acres", "accepted_area_hectares"),
		("rejected_area_acres", "rejected_area_hectares"),
	],
	"Outgrower Production Contract": [
		("contracted_area_acres", "contracted_area_hectares")
	],
	"Crop Cycle Settlement Pricing Line": [
		("eligible_area_acres", "eligible_area_hectares")
	],
	"Season Production Plan": [
		("target_acres", "target_hectares"),
		("contracted_acres", "contracted_hectares"),
		("planted_acres", "planted_hectares"),
	],
	"Season Production Target": [("target_acres", "target_hectares")],
	"Season Resource Allocation": [("target_acres", "target_hectares")],
	"Seed Harvest Quality Assessment": [
		("eligible_area_acres", "eligible_area_hectares")
	],
}


RATE_FIELDS = {
	"Outgrower Pricing Band": [
		("minimum_yield_kg_per_acre", "minimum_yield_kg_per_hectare"),
		("maximum_yield_kg_per_acre", "maximum_yield_kg_per_hectare"),
	],
	"Outgrower Pricing Policy": [
		("quota_kg_per_acre", "quota_kg_per_hectare"),
		("minimum_seed_yield_kg_per_acre", "minimum_seed_yield_kg_per_hectare"),
	],
	"Outgrower Production Contract": [
		("quota_kg_per_acre", "quota_kg_per_hectare")
	],
	"Recipe Input Item": [
		("quantity_per_acre", "quantity_per_hectare"),
		("stock_quantity_per_acre", "stock_quantity_per_hectare"),
	],
	"Crop Cycle Settlement Pricing Line": [
		("yield_kg_per_acre", "yield_kg_per_hectare")
	],
	"Season Production Target": [
		("planned_yield_kg_per_acre", "planned_yield_kg_per_hectare"),
		("parent_seed_rate_per_acre", "parent_seed_rate_per_hectare"),
	],
	"Seed Harvest Quality Assessment": [
		("provisional_yield_kg_per_acre", "provisional_yield_kg_per_hectare")
	],
}


def execute():
	for doctype, fields in AREA_FIELDS.items():
		for old_field, new_field in fields:
			_convert_column(doctype, old_field, new_field, ACRE_TO_HECTARE)
	for doctype, fields in RATE_FIELDS.items():
		for old_field, new_field in fields:
			_convert_column(doctype, old_field, new_field, PER_ACRE_TO_PER_HECTARE)

	_rename_area_achievement_field()
	_set_variety_yields_and_contract_snapshots()
	_migrate_parent_seed_rows()
	_configure_agronomy_replanting_parameter()
	_configure_categorical_isolation_controls()
	_configure_plot_naming()


def _convert_column(doctype, old_field, new_field, factor):
	table = f"tab{doctype}"
	if not frappe.db.table_exists(table):
		return
	if not frappe.db.has_column(doctype, old_field) or not frappe.db.has_column(doctype, new_field):
		return
	frappe.db.sql(
		f"""
		update `{table}`
		set `{new_field}` = `{old_field}` * %s
		where `{old_field}` is not null
		  and (`{new_field}` is null or `{new_field}` = 0)
		""",
		factor,
	)


def _rename_area_achievement_field():
	_convert_column(
		"Season Production Plan",
		"acreage_achievement_percent",
		"area_achievement_percent",
		1,
	)


def _set_variety_yields_and_contract_snapshots():
	default_yield = PER_ACRE_TO_PER_HECTARE * 1000
	if frappe.db.has_column("Crop Variety", "expected_yield_kg_per_hectare"):
		frappe.db.sql(
			"""
			update `tabCrop Variety`
			set expected_yield_kg_per_hectare = %s
			where expected_yield_kg_per_hectare is null
			   or expected_yield_kg_per_hectare = 0
			""",
			default_yield,
		)

	if frappe.db.has_column(
		"Outgrower Production Contract", "expected_yield_kg_per_hectare"
	):
		frappe.db.sql(
			"""
			update `tabOutgrower Production Contract` contract
			set expected_yield_kg_per_hectare = case
				when coalesce(contracted_area_hectares, 0) > 0
					and coalesce(expected_yield_qty, 0) > 0
				then expected_yield_qty / contracted_area_hectares
				else coalesce(
					(select crop_variety.expected_yield_kg_per_hectare
					 from `tabCrop Variety` crop_variety
					 where crop_variety.name = contract.variety),
					%s
				)
			end
			where expected_yield_kg_per_hectare is null
			   or expected_yield_kg_per_hectare = 0
			""",
			default_yield,
		)
		# The correlated fallback above is intentionally followed by a deterministic fill.
		frappe.db.sql(
			"""
			update `tabOutgrower Production Contract`
			set expected_yield_kg_per_hectare = %s
			where expected_yield_kg_per_hectare is null
			   or expected_yield_kg_per_hectare = 0
			""",
			default_yield,
		)

	if frappe.db.has_column("Crop Cycle", "expected_yield_kg_per_hectare"):
		frappe.db.sql(
			"""
			update `tabCrop Cycle` cycle
			join `tabOutgrower Production Contract` contract
			  on contract.name = cycle.production_contract
			set cycle.expected_yield_kg_per_hectare = contract.expected_yield_kg_per_hectare
			where cycle.expected_yield_kg_per_hectare is null
			   or cycle.expected_yield_kg_per_hectare = 0
			"""
		)


def _migrate_parent_seed_rows():
	if not frappe.db.table_exists("tabProduction Contract Parent Seed"):
		return
	if not frappe.db.has_column("Outgrower Production Contract", "parent_seed_item"):
		return
	contracts = frappe.db.sql(
		"""
		select name, parent_seed_item, parent_seed_uom, planned_parent_seed_qty,
			parent_seed_rate, contracted_area_hectares
		from `tabOutgrower Production Contract`
		where coalesce(parent_seed_item, '') != ''
		""",
		as_dict=True,
	)
	for contract in contracts:
		if frappe.db.exists(
			"Production Contract Parent Seed",
			{"parent": contract.name, "parentfield": "parent_seeds"},
		):
			continue
		area = flt(contract.contracted_area_hectares)
		quantity = flt(contract.planned_parent_seed_qty)
		row = frappe.get_doc(
			{
				"doctype": "Production Contract Parent Seed",
				"parent": contract.name,
				"parenttype": "Outgrower Production Contract",
				"parentfield": "parent_seeds",
				"idx": 1,
				"parent_role": "Other",
				"parent_seed_item": contract.parent_seed_item,
				"quantity_per_hectare": quantity / area if area else 0,
				"uom": contract.parent_seed_uom,
				"planned_quantity": quantity,
				"rate": contract.parent_seed_rate,
				"planned_value": quantity * flt(contract.parent_seed_rate),
			}
		)
		row.db_insert()


def _configure_agronomy_replanting_parameter():
	if frappe.db.table_exists("tabAgronomy Report Parameter"):
		frappe.db.sql(
			"""
			update `tabAgronomy Report Parameter`
			set parameter_code = 'REPLANTING_NEEDED',
				parameter_label = 'Replanting Needed?'
			where parameter_code = 'GAP_FILLING'
			"""
		)
	if frappe.db.table_exists("tabAgronomy Report Result"):
		frappe.db.sql(
			"""
			update `tabAgronomy Report Result` result
			join `tabAgronomy Report` report on report.name = result.parent
			set result.parameter_code = 'REPLANTING_NEEDED',
				result.parameter_label = 'Replanting Needed?'
			where report.docstatus = 0 and result.parameter_code = 'GAP_FILLING'
			"""
		)


def _configure_categorical_isolation_controls():
	for parameter_code in ("ISOLATION_DISTANCE", "TIME_ISOLATION"):
		name = frappe.db.get_value(
			"Inspection Parameter", {"parameter_code": parameter_code}, "name"
		)
		if not name:
			continue
		frappe.db.set_value(
			"Inspection Parameter",
			name,
			{
				"data_type": "Select",
				"select_options": "Adequate\nInadequate",
				"unit": None,
				"measurement_scope": "Inspection",
				"calculation_method": "Categorical",
			},
			update_modified=False,
		)
		standards = frappe.get_all(
			"Inspection Standard",
			filters={"parameter": name},
			fields=["name", "production_category"],
		)
		for standard in standards:
			criteria = (
				"400 metres and 6 weeks"
				if standard.production_category == "Basic"
				else "200 metres and 5 weeks"
			)
			frappe.db.set_value(
				"Inspection Standard",
				standard.name,
				{
					"comparison_rule": "Equals",
					"aggregation_method": "All Must Pass",
					"minimum_value": 0,
					"maximum_value": 0,
					"expected_text": "Adequate",
					"unit": None,
					"standard_notes": (
						f"Select Adequate only when the applicable {standard.production_category} "
						f"isolation standard is met. Reference: {criteria}."
					),
				},
				update_modified=False,
			)


def _configure_plot_naming():
	if not frappe.db.exists("DocType", "FieldOps Settings"):
		return
	frappe.db.set_single_value("FieldOps Settings", "auto_generate_plot_ids", 1)
	frappe.db.set_single_value("FieldOps Settings", "plot_alpha_suffix_limit", 2)
