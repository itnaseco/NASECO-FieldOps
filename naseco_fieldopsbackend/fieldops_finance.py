# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.naming import append_number_if_name_exists
from frappe.utils import add_days, cint, flt, getdate, nowdate

from naseco_fieldopsbackend.roles import (
	OUTGROWER_MANAGER_ROLE,
	ensure_fieldops_roles,
)


RECOVERY_POLICIES = (
	"Fully Recoverable",
	"Partially Recoverable",
	"Company Subsidy",
	"Non-Recoverable",
	"Returnable",
)

FIELDOPS_ITEMS = {
	"Maize Seed (Hybrid)": {
		"item_code": "FO-MAIZE-SEED-HYBRID",
		"uom": "Kg",
		"rate": 18000,
		"is_stock_item": 1,
	},
	"DAP Fertilizer": {
		"item_code": "FO-DAP-FERTILIZER",
		"uom": "Kg",
		"rate": 4000,
		"is_stock_item": 1,
	},
	"Urea Fertilizer": {
		"item_code": "FO-UREA-FERTILIZER",
		"uom": "Kg",
		"rate": 3500,
		"is_stock_item": 1,
	},
	"Insecticide (Lambda-cyhalothrin)": {
		"item_code": "FO-LAMBDA-CYHALOTHRIN",
		"uom": "Litre",
		"rate": 35000,
		"is_stock_item": 1,
	},
	"Fungicide (Mancozeb)": {
		"item_code": "FO-MANCOZEB",
		"uom": "Kg",
		"rate": 20000,
		"is_stock_item": 1,
	},
	"Herbicide (Glyphosate)": {
		"item_code": "FO-GLYPHOSATE",
		"uom": "Litre",
		"rate": 22000,
		"is_stock_item": 1,
	},
	"Labor - Weeding": {
		"item_code": "FO-WEEDING-LABOUR",
		"uom": "Person Day",
		"rate": 25000,
		"is_stock_item": 0,
	},
	"Maize Seed Harvest": {
		"item_code": "FO-MAIZE-SEED-HARVEST",
		"uom": "Kg",
		"rate": 2500,
		"is_stock_item": 1,
	},
	"Maize Grain": {
		"item_code": "FO-MAIZE-GRAIN",
		"uom": "Kg",
		"rate": 1200,
		"is_stock_item": 1,
	},
}


def setup_outgrower_finance():
	"""Configure the ERPNext primitives used by FieldOps finance workflows."""
	ensure_fieldops_roles()
	ensure_erpnext_custom_fields()
	ensure_crop_cycle_dimensions()

	company = get_default_company()
	if not company:
		return

	advance_account = ensure_account(
		company,
		"Advances Paid to Outgrowers",
		"Accounts Payable",
		account_type="Payable",
	)
	recoverable_account = ensure_account(
		company,
		"Recoverable Outgrower Inputs",
		"Loans and Advances (Assets)",
	)
	subsidy_account = ensure_account(
		company,
		"Outgrower Input Subsidy",
		"Direct Expenses",
	)

	company_doc = frappe.get_doc("Company", company)
	if not company_doc.book_advance_payments_in_separate_party_account:
		company_doc.book_advance_payments_in_separate_party_account = 1
	if not company_doc.default_advance_paid_account:
		company_doc.default_advance_paid_account = advance_account
	company_doc.save(ignore_permissions=True)

	settings = frappe.get_single("FieldOps Settings")
	defaults = {
		"company": company,
		"outgrower_supplier_group": get_outgrower_supplier_group(),
		"default_source_warehouse": get_default_warehouse(company, "Stores"),
		"harvest_warehouse": get_default_warehouse(company, "Raw Material"),
		"advance_paid_account": company_doc.default_advance_paid_account,
		"recoverable_inputs_account": recoverable_account,
		"input_subsidy_account": subsidy_account,
		"default_payment_account": get_default_payment_account(company),
		"default_mode_of_payment": get_default_mode_of_payment(),
		"maximum_exposure_percent": 70,
		"harvest_qa_haircut_percent": 10,
		"require_purchase_order_for_advance": 1,
	}
	for fieldname, value in defaults.items():
		if settings.meta.has_field(fieldname) and not settings.get(fieldname) and value:
			settings.set(fieldname, value)
	settings.save(ignore_permissions=True)


def ensure_finance_reference_data():
	"""Create reusable ERPNext Items and migrate legacy recipe input strings."""
	from naseco_fieldopsbackend.uom import ensure_fieldops_uoms

	ensure_fieldops_uoms()
	item_group = ensure_item_group()
	for item_name, config in FIELDOPS_ITEMS.items():
		if not frappe.db.exists("Item", config["item_code"]):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": config["item_code"],
					"item_name": item_name,
					"item_group": item_group,
					"stock_uom": config["uom"],
					"is_stock_item": config["is_stock_item"],
					"is_purchase_item": 1,
					"is_sales_item": 0,
					"standard_rate": config["rate"],
				}
			).insert(ignore_permissions=True)

	if not frappe.db.exists("DocType", "Recipe Input Item"):
		return
	for item_name, config in FIELDOPS_ITEMS.items():
		rows = frappe.get_all(
			"Recipe Input Item",
			filters={"input_name": item_name},
			pluck="name",
		)
		for row_name in rows:
			is_stock_item = config["is_stock_item"]
			frappe.db.set_value(
				"Recipe Input Item",
				row_name,
				{
					"resource_type": "Stock Item" if is_stock_item else "Service",
					"item_code": config["item_code"],
					"recovery_policy": "Fully Recoverable" if is_stock_item else "Non-Recoverable",
					"recoverable_percent": 100 if is_stock_item else 0,
					"recovery_rate_basis": "Contract Rate" if is_stock_item else None,
					"contract_recovery_rate": config["rate"] if is_stock_item else 0,
				},
				update_modified=False,
			)


def ensure_item_group():
	group_name = "Agricultural Inputs"
	if frappe.db.exists("Item Group", group_name):
		return group_name
	parent = (
		frappe.db.get_value("Item Group", {"item_group_name": "Raw Material", "is_group": 1})
		or "All Item Groups"
	)
	return frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": group_name,
			"parent_item_group": parent,
			"is_group": 0,
		}
	).insert(ignore_permissions=True).name


def ensure_erpnext_custom_fields():
	custom_fields = {
		"Supplier": [
			{
				"fieldname": "custom_outgrower",
				"label": "FieldOps Outgrower",
				"fieldtype": "Link",
				"options": "Outgrower",
				"insert_after": "supplier_name",
				"unique": 1,
				"read_only": 1,
			}
		],
		"Material Request": [
			{
				"fieldname": "custom_stage_input_request",
				"label": "Stage Input Request",
				"fieldtype": "Link",
				"options": "Stage Input Request",
				"insert_after": "title",
				"read_only": 1,
			},
			{
				"fieldname": "custom_outgrower",
				"label": "Outgrower",
				"fieldtype": "Link",
				"options": "Outgrower",
				"insert_after": "custom_stage_input_request",
				"read_only": 1,
			},
			{
				"fieldname": "custom_production_contract",
				"label": "Production Contract",
				"fieldtype": "Link",
				"options": "Outgrower Production Contract",
				"insert_after": "custom_outgrower",
				"read_only": 1,
			},
		],
		"Material Request Item": [
			{
				"fieldname": "custom_stage_input_request_item",
				"label": "Stage Input Request Item",
				"fieldtype": "Data",
				"insert_after": "cost_center",
				"read_only": 1,
			}
		]
		+ get_recovery_custom_fields("custom_stage_input_request_item"),
		"Stock Entry": [
			{
				"fieldname": "custom_stage_input_request",
				"label": "Stage Input Request",
				"fieldtype": "Link",
				"options": "Stage Input Request",
				"insert_after": "stock_entry_type",
				"read_only": 1,
			},
			{
				"fieldname": "custom_outgrower",
				"label": "Outgrower",
				"fieldtype": "Link",
				"options": "Outgrower",
				"insert_after": "custom_stage_input_request",
				"read_only": 1,
			},
			{
				"fieldname": "custom_production_contract",
				"label": "Production Contract",
				"fieldtype": "Link",
				"options": "Outgrower Production Contract",
				"insert_after": "custom_outgrower",
				"read_only": 1,
			},
		],
		"Stock Entry Detail": [
			{
				"fieldname": "custom_stage_input_request_item",
				"label": "Stage Input Request Item",
				"fieldtype": "Data",
				"insert_after": "expense_account",
				"read_only": 1,
			}
		]
		+ get_recovery_custom_fields("custom_stage_input_request_item", include_amount=True),
		"Payment Entry": [
			{
				"fieldname": "custom_crop_cycle_advance_request",
				"label": "Crop Cycle Advance Request",
				"fieldtype": "Link",
				"options": "Crop Cycle Advance Request",
				"insert_after": "payment_type",
				"read_only": 1,
			},
			{
				"fieldname": "custom_outgrower",
				"label": "Outgrower",
				"fieldtype": "Link",
				"options": "Outgrower",
				"insert_after": "custom_crop_cycle_advance_request",
				"read_only": 1,
			},
			{
				"fieldname": "custom_crop_cycle_settlement",
				"label": "Crop Cycle Settlement",
				"fieldtype": "Link",
				"options": "Crop Cycle Settlement",
				"insert_after": "custom_outgrower",
				"read_only": 1,
			},
			{
				"fieldname": "custom_production_contract",
				"label": "Production Contract",
				"fieldtype": "Link",
				"options": "Outgrower Production Contract",
				"insert_after": "custom_crop_cycle_settlement",
				"read_only": 1,
			},
		],
		"Purchase Order": [
			{
				"fieldname": "custom_outgrower",
				"label": "Outgrower",
				"fieldtype": "Link",
				"options": "Outgrower",
				"insert_after": "supplier",
				"read_only": 1,
			},
			{
				"fieldname": "custom_production_contract",
				"label": "Production Contract",
				"fieldtype": "Link",
				"options": "Outgrower Production Contract",
				"insert_after": "custom_outgrower",
				"read_only": 1,
			},
			{
				"fieldname": "custom_pricing_policy",
				"label": "Pricing Policy",
				"fieldtype": "Link",
				"options": "Outgrower Pricing Policy",
				"insert_after": "custom_production_contract",
				"read_only": 1,
			},
		],
		"Purchase Receipt": [
			{
				"fieldname": "custom_outgrower",
				"label": "Outgrower",
				"fieldtype": "Link",
				"options": "Outgrower",
				"insert_after": "supplier",
				"read_only": 1,
			},
			{
				"fieldname": "custom_production_contract",
				"label": "Production Contract",
				"fieldtype": "Link",
				"options": "Outgrower Production Contract",
				"insert_after": "custom_outgrower",
				"read_only": 1,
			},
		],
		"Purchase Receipt Item": [
			{
				"fieldname": "custom_production_lot",
				"label": "Production Lot",
				"fieldtype": "Link",
				"options": "Crop Production Lot",
				"insert_after": "quality_inspection",
			},
			{
				"fieldname": "custom_seed_harvest_quality_assessment",
				"label": "Seed Harvest Quality Assessment",
				"fieldtype": "Link",
				"options": "Seed Harvest Quality Assessment",
				"insert_after": "custom_production_lot",
				"read_only": 1,
			},
		],
		"Quality Inspection": [
			{
				"fieldname": "custom_seed_harvest_quality_assessment",
				"label": "Seed Harvest Quality Assessment",
				"fieldtype": "Link",
				"options": "Seed Harvest Quality Assessment",
				"insert_after": "reference_name",
				"read_only": 1,
			},
			{
				"fieldname": "custom_crop_cycle",
				"label": "Crop Cycle",
				"fieldtype": "Link",
				"options": "Crop Cycle",
				"insert_after": "custom_seed_harvest_quality_assessment",
				"read_only": 1,
			},
			{
				"fieldname": "custom_production_lot",
				"label": "Production Lot",
				"fieldtype": "Link",
				"options": "Crop Production Lot",
				"insert_after": "custom_crop_cycle",
				"read_only": 1,
			},
			{
				"fieldname": "custom_production_contract",
				"label": "Production Contract",
				"fieldtype": "Link",
				"options": "Outgrower Production Contract",
				"insert_after": "custom_production_lot",
				"read_only": 1,
			},
		],
		"Purchase Invoice": [
			{
				"fieldname": "custom_outgrower",
				"label": "Outgrower",
				"fieldtype": "Link",
				"options": "Outgrower",
				"insert_after": "supplier",
				"read_only": 1,
			},
			{
				"fieldname": "custom_crop_cycle_settlement",
				"label": "Crop Cycle Settlement",
				"fieldtype": "Link",
				"options": "Crop Cycle Settlement",
				"insert_after": "custom_outgrower",
				"read_only": 1,
			},
			{
				"fieldname": "custom_production_contract",
				"label": "Production Contract",
				"fieldtype": "Link",
				"options": "Outgrower Production Contract",
				"insert_after": "custom_crop_cycle_settlement",
				"read_only": 1,
			},
		],
	}
	create_custom_fields(custom_fields, update=True)


def get_recovery_custom_fields(insert_after, include_amount=False):
	fields = [
		{
			"fieldname": "custom_recovery_policy",
			"label": "Recovery Policy",
			"fieldtype": "Select",
			"options": "\n" + "\n".join(RECOVERY_POLICIES),
			"insert_after": insert_after,
			"read_only": 1,
		},
		{
			"fieldname": "custom_recoverable_percent",
			"label": "Recoverable %",
			"fieldtype": "Percent",
			"insert_after": "custom_recovery_policy",
			"read_only": 1,
		},
		{
			"fieldname": "custom_recovery_rate_basis",
			"label": "Recovery Rate Basis",
			"fieldtype": "Select",
			"options": "\nActual Valuation\nStandard Rate\nContract Rate",
			"insert_after": "custom_recoverable_percent",
			"read_only": 1,
		},
		{
			"fieldname": "custom_contract_recovery_rate",
			"label": "Contract Recovery Rate",
			"fieldtype": "Currency",
			"insert_after": "custom_recovery_rate_basis",
			"read_only": 1,
		},
	]
	if include_amount:
		fields.append(
			{
				"fieldname": "custom_recoverable_amount",
				"label": "Recoverable Amount",
				"fieldtype": "Currency",
				"insert_after": "custom_contract_recovery_rate",
				"read_only": 1,
			}
		)
	return fields


def ensure_crop_cycle_dimensions():
	if not frappe.db.exists("Accounting Dimension", {"document_type": "Crop Cycle"}):
		dimension = frappe.get_doc(
			{
				"doctype": "Accounting Dimension",
				"document_type": "Crop Cycle",
				"label": "Crop Cycle",
				"fieldname": "crop_cycle",
				"disabled": 0,
			}
		).insert(ignore_permissions=True)

		# Migrations must finish with the fields available immediately.
		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
			make_dimension_in_accounting_doctypes,
		)

		make_dimension_in_accounting_doctypes(dimension)

	if not frappe.db.exists("Inventory Dimension", {"reference_document": "Crop Cycle"}):
		frappe.get_doc(
			{
				"doctype": "Inventory Dimension",
				"dimension_name": "Crop Cycle",
				"reference_document": "Crop Cycle",
				"apply_to_all_doctypes": 1,
				"disabled": 0,
				"reqd": 0,
				"validate_negative_stock": 0,
			}
		).insert(ignore_permissions=True)


def ensure_account(company, account_name, parent_account_name, account_type=None):
	existing = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": account_name},
	)
	if existing:
		return existing

	parent = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"account_name": parent_account_name,
			"is_group": 1,
		},
	)
	if not parent:
		frappe.throw(
			_("Could not find account group {0} for {1}.").format(
				frappe.bold(parent_account_name),
				frappe.bold(company),
			)
		)

	account = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": account_name,
			"parent_account": parent,
			"company": company,
			"is_group": 0,
			"account_type": account_type,
		}
	).insert(ignore_permissions=True)
	return account.name


def get_default_company(company=None):
	if company and frappe.db.exists("Company", company):
		return company

	settings_company = None
	if frappe.db.exists("DocType", "FieldOps Settings"):
		settings_company = frappe.db.get_single_value("FieldOps Settings", "company")
	if settings_company:
		return settings_company

	default_company = frappe.defaults.get_global_default("company")
	if default_company and frappe.db.exists("Company", default_company):
		return default_company

	return frappe.db.get_value("Company", {"name": ["not like", r"\_Test%"]}, "name")


def get_outgrower_supplier_group():
	for name in ("Out Grower", "Outgrowers", "Outgrower"):
		if frappe.db.exists("Supplier Group", name):
			return name

	return frappe.get_doc(
		{
			"doctype": "Supplier Group",
			"supplier_group_name": "Outgrowers",
			"parent_supplier_group": "All Supplier Groups",
			"is_group": 0,
		}
	).insert(ignore_permissions=True).name


def get_default_warehouse(company, preferred_name=None):
	if preferred_name:
		warehouse = frappe.db.get_value(
			"Warehouse",
			{
				"company": company,
				"warehouse_name": preferred_name,
				"is_group": 0,
				"disabled": 0,
			},
		)
		if warehouse:
			return warehouse

	return frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 0, "disabled": 0},
		"name",
	)


def get_default_payment_account(company):
	for account_type in ("Bank", "Cash"):
		account = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"account_type": account_type,
				"is_group": 0,
				"disabled": 0,
			},
		)
		if account:
			return account
	return None


def get_default_mode_of_payment():
	for name in ("Wire Transfer", "Cheque", "Cash"):
		if frappe.db.exists("Mode of Payment", name):
			return name
	return frappe.db.get_value("Mode of Payment", {"enabled": 1}, "name")


def require_outgrower_manager():
	if frappe.session.user == "Administrator":
		return
	roles = set(frappe.get_roles())
	if OUTGROWER_MANAGER_ROLE not in roles and "System Manager" not in roles:
		frappe.throw(
			_("Only an Outgrower Manager or System Manager can perform this action."),
			frappe.PermissionError,
		)


@frappe.whitelist()
def ensure_outgrower_supplier(outgrower):
	require_outgrower_manager()
	return create_or_get_outgrower_supplier(outgrower)


def create_or_get_outgrower_supplier(outgrower):
	"""Return the Supplier linked to an Outgrower, creating it when needed."""
	outgrower_doc = frappe.get_doc("Outgrower", outgrower) if isinstance(outgrower, str) else outgrower

	if outgrower_doc.supplier and frappe.db.exists("Supplier", outgrower_doc.supplier):
		return outgrower_doc.supplier

	existing = None
	if frappe.get_meta("Supplier").has_field("custom_outgrower"):
		existing = frappe.db.get_value("Supplier", {"custom_outgrower": outgrower_doc.name})
	if existing:
		outgrower_doc.db_set("supplier", existing)
		return existing

	supplier_type = "Company" if outgrower_doc.outgrower_type in ("Company", "Cooperative") else "Individual"
	supplier_values = {
		"doctype": "Supplier",
		"supplier_name": outgrower_doc.full_name,
		"supplier_group": get_outgrower_supplier_group(),
		"supplier_type": supplier_type,
		"mobile_no": outgrower_doc.phone,
		"email_id": outgrower_doc.email,
	}
	if frappe.get_meta("Supplier").has_field("custom_outgrower"):
		supplier_values["custom_outgrower"] = outgrower_doc.name

	supplier_name = None
	if frappe.defaults.get_global_default("supp_master_name") == "Supplier Name":
		supplier_name = append_number_if_name_exists("Supplier", outgrower_doc.full_name)

	supplier = frappe.get_doc(supplier_values).insert(
		ignore_permissions=True,
		set_name=supplier_name,
	)
	outgrower_doc.db_set("supplier", supplier.name)
	return supplier.name


def get_crop_cycle_context(crop_cycle, ensure_supplier=False):
	cycle = frappe.get_doc("Crop Cycle", crop_cycle) if isinstance(crop_cycle, str) else crop_cycle
	plot = frappe.get_doc("Farm Plot", cycle.plot)
	outgrower = frappe.get_doc("Outgrower", plot.outgrower)
	supplier = outgrower.supplier
	if ensure_supplier and not supplier:
		supplier = ensure_outgrower_supplier(outgrower.name)
	return frappe._dict(
		cycle=cycle,
		production_contract=cycle.production_contract,
		plot=plot,
		outgrower=outgrower,
		supplier=supplier,
		company=cycle.company or get_default_company(),
	)


@frappe.whitelist()
def create_crop_cycle_purchase_order(crop_cycle):
	require_outgrower_manager()
	context = get_crop_cycle_context(crop_cycle, ensure_supplier=True)
	cycle = context.cycle

	if cycle.purchase_order and frappe.db.exists("Purchase Order", cycle.purchase_order):
		return cycle.purchase_order
	if not cycle.harvest_item or not flt(cycle.expected_yield_qty):
		frappe.throw(_("Harvest Item and Expected Yield Quantity are required."))

	settings = frappe.get_single("FieldOps Settings")
	production_contract = frappe.get_doc(
		"Outgrower Production Contract",
		cycle.production_contract,
	)
	order_qty = flt(
		production_contract.contracted_quota_qty or cycle.expected_yield_qty
	)
	order_rate = flt(
		production_contract.advance_valuation_rate or cycle.contract_rate
	)
	if order_qty <= 0 or order_rate <= 0:
		frappe.throw(
			_(
				"A positive contracted quota and advance valuation rate are required "
				"before creating the Purchase Order."
			)
		)
	schedule_date = max(
		getdate(cycle.expected_harvest_date or cycle.start_date or nowdate()),
		getdate(nowdate()),
	)
	order = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"supplier": context.supplier,
			"company": context.company,
			"transaction_date": nowdate(),
			"schedule_date": schedule_date,
			"custom_outgrower": context.outgrower.name,
			"custom_production_contract": cycle.production_contract,
			"custom_pricing_policy": production_contract.pricing_policy,
			"payment_terms_template": production_contract.payment_terms_template,
			"crop_cycle": cycle.name,
			"set_warehouse": settings.harvest_warehouse,
			"items": [
				{
					"item_code": cycle.harvest_item,
					"qty": order_qty,
					"rate": order_rate,
					"schedule_date": schedule_date,
					"warehouse": settings.harvest_warehouse,
					"crop_cycle": cycle.name,
				}
			],
		}
	)
	order.insert(ignore_permissions=True)
	cycle.db_set("purchase_order", order.name)
	return order.name


def create_material_request_from_input_request(input_request):
	request = (
		frappe.get_doc("Stage Input Request", input_request)
		if isinstance(input_request, str)
		else input_request
	)
	if request.material_request and frappe.db.exists("Material Request", request.material_request):
		return request.material_request

	context = get_crop_cycle_context(request.crop_cycle, ensure_supplier=True)
	settings = frappe.get_single("FieldOps Settings")
	required_by = max(
		getdate(request.required_by or nowdate()),
		getdate(nowdate()),
	)
	source_warehouse = request.source_warehouse or settings.default_source_warehouse
	if not source_warehouse:
		frappe.throw(_("Default Input Source Warehouse is required in FieldOps Settings."))

	items = []
	for row in request.items:
		qty = flt(row.approved_qty or row.requested_qty)
		if qty <= 0:
			continue
		items.append(
			{
				"item_code": row.item_code,
				"qty": qty,
				"uom": row.uom,
				"conversion_factor": row.conversion_factor,
				"schedule_date": required_by,
				"warehouse": row.source_warehouse or source_warehouse,
				"crop_cycle": request.crop_cycle,
				"custom_stage_input_request_item": row.name,
				"custom_recovery_policy": row.recovery_policy,
				"custom_recoverable_percent": row.recoverable_percent,
				"custom_recovery_rate_basis": row.recovery_rate_basis,
				"custom_contract_recovery_rate": row.contract_recovery_rate,
			}
		)
	if not items:
		frappe.throw(_("At least one approved stock input is required."))

	material_request = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Material Issue",
			"company": context.company,
			"transaction_date": nowdate(),
			"schedule_date": required_by,
			"set_warehouse": source_warehouse,
			"title": f"Crop inputs for {request.crop_cycle}",
			"custom_stage_input_request": request.name,
			"custom_outgrower": context.outgrower.name,
			"custom_production_contract": request.production_contract,
			"items": items,
		}
	)
	material_request.insert(ignore_permissions=True)
	request.db_set(
		{
			"material_request": material_request.name,
			"status": "Approved",
		},
		update_modified=False,
	)
	create_todo(
		settings.stores_approver,
		"Material Request",
		material_request.name,
		f"Review and fulfil crop inputs for {request.crop_cycle}",
		required_by,
		"High",
	)
	return material_request.name


def create_payment_entry_from_advance_request(advance_request):
	request = (
		frappe.get_doc("Crop Cycle Advance Request", advance_request)
		if isinstance(advance_request, str)
		else advance_request
	)
	if request.payment_entry and frappe.db.exists("Payment Entry", request.payment_entry):
		return request.payment_entry

	settings = frappe.get_single("FieldOps Settings")
	amount = flt(request.approved_amount)
	if amount <= 0:
		frappe.throw(_("Approved Amount must be greater than zero."))

	purchase_order = request.purchase_order
	if purchase_order and frappe.db.get_value("Purchase Order", purchase_order, "docstatus") == 1:
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		payment_entry = get_payment_entry("Purchase Order", purchase_order)
		payment_entry.paid_amount = amount
		payment_entry.received_amount = amount
		for reference in payment_entry.references:
			reference.allocated_amount = amount if reference.reference_name == purchase_order else 0
	else:
		payment_entry = frappe.new_doc("Payment Entry")
		payment_entry.update(
			{
				"payment_type": "Pay",
				"party_type": "Supplier",
				"party": request.supplier,
				"company": request.company,
				"posting_date": request.request_date or nowdate(),
				"paid_from": request.paid_from_account or settings.default_payment_account,
				"paid_to": settings.advance_paid_account,
				"paid_amount": amount,
				"received_amount": amount,
				"source_exchange_rate": 1,
				"target_exchange_rate": 1,
			}
		)

	payment_entry.mode_of_payment = request.mode_of_payment or settings.default_mode_of_payment
	payment_entry.reference_no = request.name
	payment_entry.reference_date = request.request_date or nowdate()
	payment_entry.custom_crop_cycle_advance_request = request.name
	payment_entry.custom_outgrower = request.outgrower
	payment_entry.custom_production_contract = request.production_contract
	if payment_entry.meta.has_field("crop_cycle"):
		payment_entry.crop_cycle = request.crop_cycle
	payment_entry.remarks = request.purpose or f"Crop-cycle advance for {request.crop_cycle}"
	payment_entry.insert(ignore_permissions=True)

	request.db_set(
		{
			"payment_entry": payment_entry.name,
			"status": "Payment Draft",
		},
		update_modified=False,
	)
	create_todo(
		settings.finance_approver,
		"Payment Entry",
		payment_entry.name,
		f"Review outgrower advance for {request.crop_cycle}",
		request.request_date,
		"High",
	)
	return payment_entry.name


def populate_stock_entry_context(doc, method=None):
	request_names = {row.material_request for row in doc.items if row.material_request}
	if len(request_names) != 1:
		return

	material_request = frappe.get_doc("Material Request", request_names.pop())
	if not material_request.custom_stage_input_request:
		return

	doc.custom_stage_input_request = material_request.custom_stage_input_request
	doc.custom_outgrower = material_request.custom_outgrower
	doc.custom_production_contract = material_request.custom_production_contract
	if doc.meta.has_field("crop_cycle"):
		doc.crop_cycle = material_request.get("crop_cycle")

	for row in doc.items:
		if not row.material_request_item:
			continue
		source = frappe.get_doc("Material Request Item", row.material_request_item)
		for fieldname in (
			"crop_cycle",
			"custom_stage_input_request_item",
			"custom_recovery_policy",
			"custom_recoverable_percent",
			"custom_recovery_rate_basis",
			"custom_contract_recovery_rate",
		):
			if row.meta.has_field(fieldname):
				row.set(fieldname, source.get(fieldname))

		rate = get_recovery_rate(row)
		row.custom_recoverable_amount = flt(row.transfer_qty or row.qty) * rate * flt(
			row.custom_recoverable_percent
		) / 100

		if is_recoverable(row.custom_recovery_policy):
			recovery_account = frappe.db.get_single_value(
				"FieldOps Settings",
				"recoverable_inputs_account",
			)
			if recovery_account:
				row.expense_account = recovery_account


def populate_purchase_receipt_context(doc, method=None):
	if doc.custom_production_contract:
		return
	purchase_orders = {
		row.purchase_order for row in doc.items if row.purchase_order
	}
	if len(purchase_orders) != 1:
		return
	purchase_order = frappe.get_doc("Purchase Order", purchase_orders.pop())
	doc.custom_outgrower = purchase_order.custom_outgrower
	doc.custom_production_contract = purchase_order.custom_production_contract
	if doc.meta.has_field("crop_cycle"):
		doc.crop_cycle = purchase_order.get("crop_cycle")


def get_recovery_rate(row):
	if row.custom_recovery_rate_basis == "Contract Rate":
		return flt(row.custom_contract_recovery_rate)
	if row.custom_recovery_rate_basis == "Standard Rate":
		return flt(row.basic_rate)
	return flt(row.valuation_rate or row.basic_rate)


def is_recoverable(policy):
	return policy in ("Fully Recoverable", "Partially Recoverable")


def sync_input_request_from_stock(doc, method=None):
	if not doc.custom_stage_input_request:
		return
	request = frappe.get_doc("Stage Input Request", doc.custom_stage_input_request)
	request.update_fulfillment_status()


def sync_advance_request_from_payment(doc, method=None):
	if doc.custom_crop_cycle_advance_request:
		status = "Paid" if doc.docstatus == 1 else "Payment Cancelled"
		frappe.db.set_value(
			"Crop Cycle Advance Request",
			doc.custom_crop_cycle_advance_request,
			{
				"status": status,
				"paid_amount": flt(doc.paid_amount) if doc.docstatus == 1 else 0,
				"payment_date": doc.posting_date if doc.docstatus == 1 else None,
			},
			update_modified=False,
		)

	if doc.custom_crop_cycle_settlement:
		settlement = frappe.db.get_value(
			"Crop Cycle Settlement",
			doc.custom_crop_cycle_settlement,
			"purchase_invoice",
		)
		invoice_status = (
			frappe.db.get_value(
				"Purchase Invoice",
				settlement,
				["docstatus", "outstanding_amount"],
				as_dict=True,
			)
			if settlement
			else None
		)
		status = "Posted"
		if invoice_status and invoice_status.docstatus == 1 and flt(invoice_status.outstanding_amount) <= 0:
			status = "Paid"
		frappe.db.set_value(
			"Crop Cycle Settlement",
			doc.custom_crop_cycle_settlement,
			"status",
			status,
			update_modified=False,
		)


def sync_settlement_from_invoice(doc, method=None):
	if not doc.custom_crop_cycle_settlement:
		return
	status = "Posted" if doc.docstatus == 1 else "Invoice Cancelled"
	if doc.docstatus == 1 and flt(doc.outstanding_amount) <= 0:
		status = "Paid"
	frappe.db.set_value(
		"Crop Cycle Settlement",
		doc.custom_crop_cycle_settlement,
		{
			"status": status,
			"purchase_invoice": doc.name,
		},
		update_modified=False,
	)


def populate_settlement_sources(settlement):
	"""Refresh source-voucher snapshots without making them accounting records."""
	crop_cycle = settlement.crop_cycle
	settlement.set("harvest_receipts", [])
	settlement.set("pricing_lines", [])
	settlement.set("stock_inputs", [])
	settlement.set("cash_advances", [])

	receipt_rows = frappe.db.sql(
		"""
		select
			receipt.name as purchase_receipt,
			item.name as purchase_receipt_item,
			receipt.posting_date,
			item.item_code,
			item.qty as accepted_qty,
			item.uom,
			item.base_net_rate as rate,
			item.base_net_amount as amount
		from `tabPurchase Receipt Item` item
		inner join `tabPurchase Receipt` receipt on receipt.name = item.parent
		where receipt.docstatus = 1
			and (
				item.crop_cycle = %(crop_cycle)s
				or (
					%(purchase_order)s is not null
					and item.purchase_order = %(purchase_order)s
				)
			)
		order by receipt.posting_date, receipt.name, item.idx
		""",
		{
			"crop_cycle": crop_cycle,
			"purchase_order": settlement.purchase_order,
		},
		as_dict=True,
	)
	for row in receipt_rows:
		settlement.append("harvest_receipts", row)

	populate_settlement_pricing(settlement)

	stock_rows = frappe.db.sql(
		"""
		select
			entry.name as stock_entry,
			detail.name as stock_entry_detail,
			entry.posting_date,
			detail.item_code,
			coalesce(detail.transfer_qty, detail.qty) as qty,
			detail.stock_uom as uom,
			detail.custom_recovery_policy as recovery_policy,
			detail.custom_recoverable_percent as recoverable_percent,
			case
				when coalesce(detail.transfer_qty, detail.qty) = 0 then 0
				else detail.custom_recoverable_amount
					/ coalesce(detail.transfer_qty, detail.qty)
			end as recovery_rate,
			detail.custom_recoverable_amount as recoverable_amount
		from `tabStock Entry Detail` detail
		inner join `tabStock Entry` entry on entry.name = detail.parent
		where entry.docstatus = 1
			and detail.crop_cycle = %(crop_cycle)s
			and coalesce(detail.custom_recoverable_amount, 0) > 0
		order by entry.posting_date, entry.name, detail.idx
		""",
		{"crop_cycle": crop_cycle},
		as_dict=True,
	)
	for row in stock_rows:
		settlement.append("stock_inputs", row)

	advance_rows = frappe.db.sql(
		"""
		select
			request.name as advance_request,
			payment.name as payment_entry,
			payment.posting_date as payment_date,
			payment.paid_amount,
			greatest(
				payment.paid_amount - coalesce(allocated.allocated_amount, 0),
				0
			) as available_amount
		from `tabCrop Cycle Advance Request` request
		inner join `tabPayment Entry` payment on payment.name = request.payment_entry
		left join (
			select
				advance.reference_name,
				sum(advance.allocated_amount) as allocated_amount
			from `tabPurchase Invoice Advance` advance
			inner join `tabPurchase Invoice` invoice on invoice.name = advance.parent
			where invoice.docstatus = 1
				and advance.reference_type = 'Payment Entry'
			group by advance.reference_name
		) allocated on allocated.reference_name = payment.name
		where request.docstatus = 1
			and request.crop_cycle = %(crop_cycle)s
			and payment.docstatus = 1
		order by payment.posting_date, payment.name
		""",
		{"crop_cycle": crop_cycle},
		as_dict=True,
	)
	for row in advance_rows:
		if flt(row.available_amount) > 0:
			settlement.append("cash_advances", row)


def populate_settlement_pricing(settlement):
	"""Aggregate submitted laboratory assessments into contract pricing by production lot."""
	if not settlement.production_contract:
		return
	policy_name = frappe.db.get_value(
		"Outgrower Production Contract",
		settlement.production_contract,
		"pricing_policy",
	)
	settlement.pricing_policy = policy_name
	if not policy_name:
		return

	from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_pricing_policy.outgrower_pricing_policy import (
		calculate_harvest_pricing,
	)

	policy = frappe.get_doc("Outgrower Pricing Policy", policy_name)
	assessments = frappe.get_all(
		"Seed Harvest Quality Assessment",
		filters={"crop_cycle": settlement.crop_cycle, "docstatus": 1},
		fields=[
			"name",
			"production_lot",
			"purchase_receipt_item",
			"net_dry_qty",
			"uom",
			"germination_percent",
			"genetic_purity_percent",
			"undersize_percent",
			"reject_percent",
			"disposition",
			"delivery_date",
			"bonus_status",
		],
		order_by="production_lot, delivery_date, name",
	)
	grouped = {}
	for assessment in assessments:
		grouped.setdefault(assessment.production_lot, []).append(assessment)

	delivery_dates = []
	for production_lot, rows in grouped.items():
		lot = frappe.db.get_value(
			"Crop Production Lot",
			production_lot,
			["area_acres", "accepted_area_acres"],
			as_dict=True,
		)
		if not lot:
			continue
		billable = [row for row in rows if row.disposition != "Rejected"]
		pricing_rows = billable or rows
		qty = sum(flt(row.net_dry_qty) for row in pricing_rows)
		if qty <= 0:
			continue
		area = flt(lot.accepted_area_acres or lot.area_acres)
		if area <= 0:
			frappe.throw(
				_("Production Lot {0} needs positive eligible acreage for pricing.").format(
					frappe.bold(production_lot)
				)
			)

		def weighted(fieldname):
			return sum(
				flt(row.get(fieldname)) * flt(row.net_dry_qty)
				for row in pricing_rows
			) / qty

		result = calculate_harvest_pricing(
			policy,
			qty,
			area,
			weighted("genetic_purity_percent"),
			weighted("germination_percent"),
			weighted("undersize_percent"),
			weighted("reject_percent"),
			force_rejected=not billable,
		)
		bonus_status = (
			"Pending QA Approval"
			if result.potential_bonus_amount
			else "Not Eligible"
		)
		settlement.append(
			"pricing_lines",
			{
				"production_lot": production_lot,
				"assessment_count": len(rows),
				"net_dry_qty": result.net_dry_qty,
				"uom": "Kg",
				"eligible_area_acres": result.eligible_area_acres,
				"yield_kg_per_acre": result.yield_kg_per_acre,
				"genetic_purity_percent": weighted("genetic_purity_percent"),
				"germination_percent": weighted("germination_percent"),
				"undersize_percent": weighted("undersize_percent"),
				"reject_percent": weighted("reject_percent"),
				"pricing_band": result.pricing_band,
				"price_basis": result.price_basis,
				"base_quota_qty": result.base_quota_qty,
				"base_rate": result.base_rate,
				"excess_qty": result.excess_qty,
				"excess_rate": result.excess_rate,
				"grain_qty": result.grain_qty,
				"gross_value": result.gross_value,
				"screen_deduction": result.screen_deduction,
				"reject_deduction": result.reject_deduction,
				"initial_payable_value": result.initial_payable_value,
				"potential_bonus_rate": result.potential_bonus_rate,
				"potential_bonus_amount": result.potential_bonus_amount,
				"bonus_status": bonus_status,
			},
		)
		delivery_dates.extend(row.delivery_date for row in rows if row.delivery_date)

	if delivery_dates:
		first_delivery = min(getdate(value) for value in delivery_dates)
		settlement.payment_due_date = add_days(
			first_delivery,
			cint(policy.payment_due_days),
		)
		settlement.bonus_review_due_date = add_days(
			first_delivery,
			cint(policy.bonus_payment_days),
		)


def create_purchase_invoice_from_settlement(settlement):
	if settlement.purchase_invoice and frappe.db.exists(
		"Purchase Invoice", settlement.purchase_invoice
	):
		if frappe.db.get_value(
			"Purchase Invoice", settlement.purchase_invoice, "docstatus"
		) != 2:
			return settlement.purchase_invoice

	receipt_names = list(
		dict.fromkeys(row.purchase_receipt for row in settlement.harvest_receipts)
	)
	if not receipt_names:
		frappe.throw(_("No submitted Purchase Receipt is available for settlement."))
	if flt(settlement.gross_harvest_value) <= 0:
		settlement.db_set("status", "Shortfall", update_modified=False)
		return None

	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
		make_purchase_invoice,
	)

	invoice = None
	for receipt_name in receipt_names:
		invoice = make_purchase_invoice(receipt_name, target_doc=invoice)

	invoice.posting_date = settlement.posting_date
	invoice.custom_outgrower = settlement.outgrower
	invoice.custom_crop_cycle_settlement = settlement.name
	invoice.custom_production_contract = settlement.production_contract
	if invoice.meta.has_field("crop_cycle"):
		invoice.crop_cycle = settlement.crop_cycle
	apply_contract_pricing_to_invoice(invoice, settlement)

	settings = frappe.get_single("FieldOps Settings")
	if flt(settlement.stock_recovery_to_deduct):
		if not settings.recoverable_inputs_account:
			frappe.throw(
				_("Recoverable Inputs Account is required in FieldOps Settings.")
			)
		invoice.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": settings.recoverable_inputs_account,
				"description": f"Recoverable crop inputs for {settlement.crop_cycle}",
				"category": "Total",
				"add_deduct_tax": "Deduct",
				"tax_amount": settlement.stock_recovery_to_deduct,
			},
		)

	for adjustment in settlement.adjustments:
		invoice.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": adjustment.account,
				"description": adjustment.description,
				"category": "Total",
				"add_deduct_tax": adjustment.add_or_deduct,
				"tax_amount": adjustment.amount,
			},
		)

	invoice.run_method("calculate_taxes_and_totals")
	invoice.set_advances()
	limit_invoice_advances(invoice, settlement)
	invoice.insert(ignore_permissions=True)
	settlement.db_set(
		{
			"purchase_invoice": invoice.name,
			"status": "Invoice Draft",
		},
		update_modified=False,
	)
	create_todo(
		settings.finance_approver,
		"Purchase Invoice",
		invoice.name,
		f"Review crop-cycle settlement for {settlement.crop_cycle}",
		settlement.posting_date,
		"High",
	)
	return invoice.name


def apply_contract_pricing_to_invoice(invoice, settlement):
	"""Replace provisional receipt rates with the approved contract assessment value."""
	target_base_value = flt(settlement.gross_harvest_value)
	total_qty = sum(flt(row.qty) for row in invoice.items)
	if target_base_value <= 0 or total_qty <= 0:
		frappe.throw(_("A positive assessed harvest value and invoice quantity are required."))

	conversion_rate = flt(invoice.conversion_rate) or 1
	rate = target_base_value / total_qty / conversion_rate
	for row in invoice.items:
		row.rate = rate
		row.price_list_rate = rate
		row.discount_percentage = 0
		row.discount_amount = 0
	invoice.run_method("calculate_taxes_and_totals")


def limit_invoice_advances(invoice, settlement):
	allowed = {
		row.payment_entry: flt(row.available_amount)
		for row in settlement.cash_advances
		if row.payment_entry
	}
	remaining = flt(settlement.cash_advance_to_allocate)
	selected = []
	for row in invoice.advances:
		if row.reference_type != "Payment Entry" or row.reference_name not in allowed:
			continue
		row.allocated_amount = min(
			flt(row.advance_amount),
			allowed[row.reference_name],
			remaining,
		)
		if row.allocated_amount > 0:
			selected.append(row)
			remaining -= row.allocated_amount
		if remaining <= 0:
			break
	invoice.set("advances", selected)


def get_payment_status(payment_entry):
	if not payment_entry:
		return None
	return frappe.db.get_value("Payment Entry", payment_entry, "docstatus")


def get_stock_recovery(crop_cycle):
	meta = frappe.get_meta("Stock Entry Detail")
	if not meta.has_field("crop_cycle") or not meta.has_field("custom_recoverable_amount"):
		return 0

	return flt(
		frappe.db.sql(
			"""
			select coalesce(sum(detail.custom_recoverable_amount), 0)
			from `tabStock Entry Detail` detail
			inner join `tabStock Entry` entry on entry.name = detail.parent
			where entry.docstatus = 1 and detail.crop_cycle = %s
			""",
			crop_cycle,
		)[0][0]
	)


def get_cash_advances(crop_cycle):
	rows = frappe.get_all(
		"Crop Cycle Advance Request",
		filters={"crop_cycle": crop_cycle, "docstatus": 1},
		fields=["payment_entry", "approved_amount"],
	)
	submitted = 0
	pending = 0
	for row in rows:
		docstatus = get_payment_status(row.payment_entry)
		if docstatus == 1:
			submitted += flt(
				frappe.db.get_value("Payment Entry", row.payment_entry, "paid_amount")
			)
		elif docstatus != 2:
			pending += flt(row.approved_amount)
	return submitted, pending


def get_harvest_value(crop_cycle, purchase_order=None):
	item_meta = frappe.get_meta("Purchase Receipt Item")
	if item_meta.has_field("crop_cycle"):
		return flt(
			frappe.db.sql(
				"""
				select coalesce(sum(item.base_net_amount), 0)
				from `tabPurchase Receipt Item` item
				inner join `tabPurchase Receipt` receipt on receipt.name = item.parent
				where receipt.docstatus = 1 and item.crop_cycle = %s
				""",
				crop_cycle,
			)[0][0]
		)
	if purchase_order:
		return flt(
			frappe.db.sql(
				"""
				select coalesce(sum(item.base_net_amount), 0)
				from `tabPurchase Receipt Item` item
				inner join `tabPurchase Receipt` receipt on receipt.name = item.parent
				where receipt.docstatus = 1 and item.purchase_order = %s
				""",
				purchase_order,
			)[0][0]
		)
	return 0


@frappe.whitelist()
def calculate_crop_cycle_exposure(crop_cycle):
	context = get_crop_cycle_context(crop_cycle)
	cycle = context.cycle
	settings = frappe.get_single("FieldOps Settings")
	expected_value = flt(cycle.expected_harvest_value)
	max_percent = flt(cycle.max_exposure_percent or settings.maximum_exposure_percent or 70)
	qa_haircut = flt(settings.harvest_qa_haircut_percent)
	risk_adjusted_value = expected_value * max(100 - qa_haircut, 0) / 100
	stock_recovery = get_stock_recovery(cycle.name)
	cash_advanced, pending_cash = get_cash_advances(cycle.name)
	actual_harvest = get_harvest_value(cycle.name, cycle.purchase_order)
	exposure = stock_recovery + cash_advanced
	committed_exposure = exposure + pending_cash
	limit_amount = risk_adjusted_value * max_percent / 100

	return frappe._dict(
		expected_harvest_value=expected_value,
		risk_adjusted_harvest_value=risk_adjusted_value,
		maximum_exposure_percent=max_percent,
		exposure_limit=limit_amount,
		recoverable_stock_value=stock_recovery,
		cash_advanced=cash_advanced,
		pending_cash_advance=pending_cash,
		total_exposure=exposure,
		committed_exposure=committed_exposure,
		available_advance_capacity=max(limit_amount - committed_exposure, 0),
		actual_harvest_value=actual_harvest,
		forecast_net_payable=expected_value - committed_exposure,
		actual_net_position=actual_harvest - exposure,
	)


def create_todo(allocated_to, reference_type, reference_name, description, date=None, priority="Medium"):
	if not allocated_to:
		return
	if frappe.db.exists(
		"ToDo",
		{
			"reference_type": reference_type,
			"reference_name": reference_name,
			"allocated_to": allocated_to,
			"status": "Open",
		},
	):
		return
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": allocated_to,
			"reference_type": reference_type,
			"reference_name": reference_name,
			"description": description,
			"date": getdate(date) if date else None,
			"status": "Open",
			"priority": priority,
		}
	).insert(ignore_permissions=True)


def get_finance_setup_health():
	"""Return a concise setup snapshot for deployment verification."""
	company = get_default_company()
	settings = frappe.get_single("FieldOps Settings")
	accounts = frappe.get_all(
		"Account",
		filters={
			"company": company,
			"account_name": [
				"in",
				[
					"Advances Paid to Outgrowers",
					"Recoverable Outgrower Inputs",
					"Outgrower Input Subsidy",
				],
			],
		},
		fields=["name", "account_name", "account_type", "root_type"],
		order_by="account_name",
	)
	return {
		"company": company,
		"separate_supplier_advance_accounting": cint(
			frappe.db.get_value(
				"Company",
				company,
				"book_advance_payments_in_separate_party_account",
			)
		),
		"default_advance_paid_account": frappe.db.get_value(
			"Company",
			company,
			"default_advance_paid_account",
		),
		"accounts": accounts,
		"accounting_dimension": frappe.db.exists(
			"Accounting Dimension",
			{"document_type": "Crop Cycle"},
		),
		"inventory_dimension": frappe.db.exists(
			"Inventory Dimension",
			{"reference_document": "Crop Cycle"},
		),
		"finance_item_count": frappe.db.count(
			"Item",
			{"item_code": ["in", [row["item_code"] for row in FIELDOPS_ITEMS.values()]]},
		),
		"settings": {
			"maximum_exposure_percent": settings.maximum_exposure_percent,
			"harvest_qa_haircut_percent": settings.harvest_qa_haircut_percent,
			"advance_paid_account": settings.advance_paid_account,
			"recoverable_inputs_account": settings.recoverable_inputs_account,
			"input_subsidy_account": settings.input_subsidy_account,
			"default_source_warehouse": settings.default_source_warehouse,
			"harvest_warehouse": settings.harvest_warehouse,
		},
		"sample": frappe.db.get_value(
			"Crop Cycle",
			"SAMPLE-CC-001",
			[
				"supplier",
				"harvest_item",
				"expected_yield_qty",
				"contract_rate",
				"expected_harvest_value",
			],
			as_dict=True,
		),
		"sample_documents": {
			"purchase_order": frappe.db.get_value(
				"Purchase Order",
				frappe.db.get_value("Crop Cycle", "SAMPLE-CC-001", "purchase_order"),
				["name", "docstatus", "status"],
				as_dict=True,
			),
			"input_request": frappe.db.get_value(
				"Stage Input Request",
				{"crop_cycle": "SAMPLE-CC-001", "request_id": "SAMPLE-INPUT-001"},
				["name", "docstatus", "status", "material_request"],
				as_dict=True,
			),
			"advance_request": frappe.db.get_value(
				"Crop Cycle Advance Request",
				{
					"crop_cycle": "SAMPLE-CC-001",
					"purpose": "Planting labour and field preparation",
				},
				["name", "docstatus", "status", "payment_entry"],
				as_dict=True,
			),
			"settlement_count": frappe.db.count(
				"Crop Cycle Settlement",
				{"crop_cycle": "SAMPLE-CC-001"},
			),
		},
	}


def get_contract_management_health():
	"""Return migrated contract, quality, and workspace integration status."""
	from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_pricing_policy.outgrower_pricing_policy import (
		calculate_harvest_pricing,
	)

	policy_name = "2026B Maize Certified Seed Pricing"
	policy = frappe.get_doc("Outgrower Pricing Policy", policy_name)
	sample_pricing = calculate_harvest_pricing(
		policy,
		net_dry_qty=1200,
		eligible_area_acres=1,
		genetic_purity_percent=98,
		germination_percent=97,
	)
	workspace_links = frappe.get_all(
		"Workspace Link",
		filters={"parent": "NASECO FieldOps"},
		pluck="link_to",
	)
	return {
		"pricing_policies": frappe.db.count(
			"Outgrower Pricing Policy",
			{"season": "2026 B", "docstatus": 1, "status": "Active"},
		),
		"contract_templates": frappe.db.count(
			"Production Contract Template",
			{"season": "2026 B", "docstatus": 1, "status": "Active"},
		),
		"certified_policy_band_count": len(policy.pricing_bands),
		"sample_pricing": {
			"band": sample_pricing.pricing_band,
			"basis": sample_pricing.price_basis,
			"gross_value": sample_pricing.gross_value,
			"initial_payable": sample_pricing.initial_payable_value,
			"potential_bonus": sample_pricing.potential_bonus_amount,
		},
		"custom_fields": {
			"purchase_order_pricing_policy": frappe.get_meta(
				"Purchase Order"
			).has_field("custom_pricing_policy"),
			"receipt_item_production_lot": frappe.get_meta(
				"Purchase Receipt Item"
			).has_field("custom_production_lot"),
			"quality_inspection_assessment": frappe.get_meta(
				"Quality Inspection"
			).has_field("custom_seed_harvest_quality_assessment"),
		},
		"workspace_links": {
			name: name in workspace_links
			for name in (
				"Crop Production Lot",
				"Seed Harvest Quality Assessment",
				"Quality Inspection",
				"Production Contract Template",
				"Outgrower Pricing Policy",
				"Bank Account",
			)
		},
	}


def verify_sample_finance_workflow():
	"""Exercise draft ERP voucher generation and roll back every test mutation."""
	savepoint = "fieldops_finance_verification"
	frappe.db.savepoint(savepoint)
	try:
		cycle = frappe.get_doc("Crop Cycle", "SAMPLE-CC-001")
		if not cycle.purchase_order:
			create_crop_cycle_purchase_order(cycle.name)
			cycle.reload()

		purchase_order = frappe.get_doc("Purchase Order", cycle.purchase_order)
		if purchase_order.docstatus == 0:
			purchase_order.submit()

		input_request_name = frappe.db.get_value(
			"Stage Input Request",
			{"crop_cycle": cycle.name, "request_id": "SAMPLE-INPUT-001"},
		)
		input_request = frappe.get_doc("Stage Input Request", input_request_name)
		if input_request.docstatus == 0:
			input_request.submit()
		input_request.reload()
		material_request = frappe.get_doc(
			"Material Request",
			input_request.material_request,
		)

		advance_request_name = frappe.db.get_value(
			"Crop Cycle Advance Request",
			{
				"crop_cycle": cycle.name,
				"purpose": "Planting labour and field preparation",
			},
		)
		advance_request = frappe.get_doc(
			"Crop Cycle Advance Request",
			advance_request_name,
		)
		if advance_request.docstatus == 0:
			advance_request.submit()
		advance_request.reload()
		payment_entry = frappe.get_doc(
			"Payment Entry",
			advance_request.payment_entry,
		)

		return {
			"purchase_order": {
				"name": purchase_order.name,
				"docstatus": purchase_order.docstatus,
				"supplier": purchase_order.supplier,
				"crop_cycle": purchase_order.get("crop_cycle"),
				"item": purchase_order.items[0].item_code,
				"qty": purchase_order.items[0].qty,
				"rate": purchase_order.items[0].rate,
			},
			"material_request": {
				"name": material_request.name,
				"docstatus": material_request.docstatus,
				"type": material_request.material_request_type,
				"input_request": material_request.custom_stage_input_request,
				"item": material_request.items[0].item_code,
				"qty": material_request.items[0].qty,
				"crop_cycle": material_request.items[0].get("crop_cycle"),
				"recovery_policy": material_request.items[0].custom_recovery_policy,
			},
			"payment_entry": {
				"name": payment_entry.name,
				"docstatus": payment_entry.docstatus,
				"payment_type": payment_entry.payment_type,
				"party_type": payment_entry.party_type,
				"party": payment_entry.party,
				"paid_from": payment_entry.paid_from,
				"paid_to": payment_entry.paid_to,
				"paid_amount": payment_entry.paid_amount,
				"advance_request": payment_entry.custom_crop_cycle_advance_request,
				"crop_cycle": payment_entry.get("crop_cycle"),
				"purchase_order_reference": next(
					(
						row.reference_name
						for row in payment_entry.references
						if row.reference_doctype == "Purchase Order"
					),
					None,
				),
			},
		}
	finally:
		frappe.db.rollback(save_point=savepoint)


def verify_sample_settlement_workflow():
	"""Exercise harvest receipt, advance allocation, and invoice settlement with rollback."""
	savepoint = "fieldops_settlement_verification"
	frappe.db.savepoint(savepoint)
	try:
		cycle = frappe.get_doc("Crop Cycle", "SAMPLE-CC-001")
		purchase_order = frappe.get_doc("Purchase Order", cycle.purchase_order)
		if purchase_order.docstatus == 0:
			purchase_order.submit()

		input_request_name = frappe.db.get_value(
			"Stage Input Request",
			{"crop_cycle": cycle.name, "request_id": "SAMPLE-INPUT-001"},
		)
		input_request = frappe.get_doc("Stage Input Request", input_request_name)
		if input_request.docstatus == 0:
			input_request.submit()
		input_request.reload()
		material_request = frappe.get_doc(
			"Material Request",
			input_request.material_request,
		)
		if material_request.docstatus == 0:
			material_request.submit()

		settings = frappe.get_single("FieldOps Settings")
		seed_config = FIELDOPS_ITEMS["Maize Seed (Hybrid)"]
		stock_receipt = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"company": cycle.company,
				"purpose": "Material Receipt",
				"stock_entry_type": "Material Receipt",
				"items": [
					{
						"item_code": seed_config["item_code"],
						"qty": 20,
						"t_warehouse": settings.default_source_warehouse,
						"basic_rate": seed_config["rate"],
					}
				],
			}
		)
		stock_receipt.insert(ignore_permissions=True)
		stock_receipt.submit()

		from erpnext.stock.doctype.material_request.material_request import (
			make_stock_entry,
		)

		stock_issue = make_stock_entry(material_request.name)
		stock_issue.insert(ignore_permissions=True)
		stock_issue.submit()

		advance_request_name = frappe.db.get_value(
			"Crop Cycle Advance Request",
			{
				"crop_cycle": cycle.name,
				"purpose": "Planting labour and field preparation",
			},
		)
		advance_request = frappe.get_doc(
			"Crop Cycle Advance Request",
			advance_request_name,
		)
		if advance_request.docstatus == 0:
			advance_request.submit()
		advance_request.reload()
		payment_entry = frappe.get_doc("Payment Entry", advance_request.payment_entry)
		if payment_entry.docstatus == 0:
			payment_entry.submit()

		from erpnext.buying.doctype.purchase_order.purchase_order import (
			make_purchase_receipt,
		)

		receipt = make_purchase_receipt(purchase_order.name)
		receipt.custom_outgrower = get_crop_cycle_context(cycle).outgrower.name
		if receipt.meta.has_field("crop_cycle"):
			receipt.crop_cycle = cycle.name
		for row in receipt.items:
			if row.meta.has_field("crop_cycle"):
				row.crop_cycle = cycle.name
		receipt.insert(ignore_permissions=True)
		receipt.submit()

		settlement = frappe.get_doc(
			{
				"doctype": "Crop Cycle Settlement",
				"crop_cycle": cycle.name,
				"posting_date": nowdate(),
			}
		).insert(ignore_permissions=True)
		settlement.submit()
		settlement.reload()
		invoice = frappe.get_doc("Purchase Invoice", settlement.purchase_invoice)

		return {
			"purchase_receipt": {
				"name": receipt.name,
				"docstatus": receipt.docstatus,
				"crop_cycle": receipt.items[0].get("crop_cycle"),
				"qty": receipt.items[0].qty,
				"amount": receipt.items[0].base_net_amount,
			},
			"stock_issue": {
				"name": stock_issue.name,
				"docstatus": stock_issue.docstatus,
				"crop_cycle": stock_issue.items[0].get("crop_cycle"),
				"item": stock_issue.items[0].item_code,
				"qty": stock_issue.items[0].transfer_qty,
				"recoverable_amount": stock_issue.items[0].custom_recoverable_amount,
				"recovery_account": stock_issue.items[0].expense_account,
			},
			"settlement": {
				"name": settlement.name,
				"docstatus": settlement.docstatus,
				"status": settlement.status,
				"gross_harvest_value": settlement.gross_harvest_value,
				"stock_recovery_due": settlement.stock_recovery_due,
				"stock_recovery_to_deduct": settlement.stock_recovery_to_deduct,
				"cash_advance_available": settlement.cash_advance_available,
				"cash_advance_to_allocate": settlement.cash_advance_to_allocate,
				"net_payable": settlement.net_payable,
			},
			"purchase_invoice": {
				"name": invoice.name,
				"docstatus": invoice.docstatus,
				"grand_total": invoice.grand_total,
				"recovery_deduction": sum(
					flt(row.tax_amount)
					for row in invoice.taxes
					if row.account_head == settings.recoverable_inputs_account
				),
				"allocated_advance": sum(
					flt(row.allocated_amount) for row in invoice.advances
				),
				"advance_payment_entries": [
					row.reference_name
					for row in invoice.advances
					if row.reference_type == "Payment Entry"
				],
				"settlement": invoice.custom_crop_cycle_settlement,
				"crop_cycle": invoice.get("crop_cycle"),
			},
		}
	finally:
		frappe.db.rollback(save_point=savepoint)
