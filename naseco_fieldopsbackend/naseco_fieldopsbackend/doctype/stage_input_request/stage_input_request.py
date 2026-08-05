# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from naseco_fieldopsbackend.fieldops_finance import (
	create_material_request_from_input_request,
	get_crop_cycle_context,
)
from naseco_fieldopsbackend.uom import get_item_uom_conversion


class StageInputRequest(Document):
	def before_validate(self):
		self.set_context()
		self.migrate_legacy_input()
		self.set_item_defaults()
		self.calculate_totals()

	def validate(self):
		self.validate_items()

	def before_submit(self):
		self.status = "Pending Approval"

	def on_submit(self):
		create_material_request_from_input_request(self)

	def before_cancel(self):
		self.validate_material_request_can_cancel()

	def on_cancel(self):
		if self.material_request and frappe.db.get_value(
			"Material Request", self.material_request, "docstatus"
		) == 0:
			frappe.delete_doc(
				"Material Request",
				self.material_request,
				ignore_permissions=True,
			)
		self.db_set("status", "Cancelled", update_modified=False)

	def set_context(self):
		if not self.crop_cycle:
			return
		context = get_crop_cycle_context(self.crop_cycle)
		self.production_contract = context.cycle.production_contract
		self.company = context.company
		self.outgrower = context.outgrower.name
		self.supplier = context.supplier
		self.requested_by = self.requested_by or frappe.session.user
		self.request_date = self.request_date or nowdate()
		self.required_by = self.required_by or self.request_date
		self.source_warehouse = self.source_warehouse or frappe.db.get_single_value(
			"FieldOps Settings",
			"default_source_warehouse",
		)

	def migrate_legacy_input(self):
		if self.items or not (self.input_name or self.input_type):
			return

		item_code = None
		for value in (self.input_name, self.input_type):
			if value and frappe.db.exists("Item", value):
				item_code = value
				break
			if value:
				item_code = frappe.db.get_value("Item", {"item_name": value})
				if item_code:
					break
		if not item_code:
			frappe.throw(
				_("Legacy input {0} must be mapped to a Stock Item before synchronization.").format(
					frappe.bold(self.input_name or self.input_type)
				)
			)

		self.append(
			"items",
			{
				"item_code": item_code,
				"requested_qty": self.quantity_needed or self.quantity,
				"approved_qty": self.quantity_needed or self.quantity,
				"uom": self.unit,
				"source_warehouse": self.source_warehouse,
				"recovery_policy": "Fully Recoverable",
				"recoverable_percent": 100,
				"recovery_rate_basis": "Actual Valuation",
			},
		)

	def set_item_defaults(self):
		default_recovery_policy = None
		if self.production_contract:
			default_recovery_policy = frappe.db.get_value(
				"Outgrower Production Contract",
				self.production_contract,
				"default_recovery_policy",
			)
		for row in self.items:
			if not row.item_code:
				continue
			item = frappe.db.get_value(
				"Item",
				row.item_code,
				["item_name", "stock_uom", "valuation_rate", "is_stock_item", "disabled"],
				as_dict=True,
			)
			if not item or item.disabled or not item.is_stock_item:
				frappe.throw(
					_("Item {0} must be an enabled stock Item.").format(
						frappe.bold(row.item_code)
					)
				)
			row.item_name = item.item_name
			conversion = get_item_uom_conversion(row.item_code, row.uom or item.stock_uom)
			row.uom = conversion.uom
			row.stock_uom = conversion.stock_uom
			row.conversion_factor = conversion.conversion_factor
			row.source_warehouse = row.source_warehouse or self.source_warehouse
			row.approved_qty = (
				row.requested_qty if row.approved_qty is None else row.approved_qty
			)
			row.requested_stock_qty = flt(row.requested_qty) * flt(row.conversion_factor)
			row.approved_stock_qty = flt(row.approved_qty) * flt(row.conversion_factor)
			row.issued_stock_qty = flt(row.issued_stock_qty)
			row.issued_qty = (
				flt(row.issued_stock_qty) / flt(row.conversion_factor)
				if flt(row.conversion_factor)
				else 0
			)
			row.remaining_qty = max(flt(row.approved_qty) - flt(row.issued_qty), 0)
			row.remaining_stock_qty = max(
				flt(row.approved_stock_qty) - flt(row.issued_stock_qty), 0
			)
			row.estimated_rate = flt(row.estimated_rate or item.valuation_rate)
			row.estimated_amount = flt(row.approved_stock_qty) * flt(row.estimated_rate)
			row.recovery_policy = row.recovery_policy or default_recovery_policy

			if row.recovery_policy == "Fully Recoverable":
				row.recoverable_percent = 100
			elif row.recovery_policy in ("Company Subsidy", "Non-Recoverable"):
				row.recoverable_percent = 0

	def calculate_totals(self):
		self.total_requested_value = sum(
			flt(row.requested_stock_qty) * flt(row.estimated_rate) for row in self.items
		)
		self.total_approved_value = sum(
			flt(row.approved_stock_qty) * flt(row.estimated_rate) for row in self.items
		)
		self.quantity_needed = sum(flt(row.approved_qty) for row in self.items)
		self.quantity_dispatched = sum(flt(row.issued_qty) for row in self.items)
		self.quantity_remaining = max(
			flt(self.quantity_needed) - flt(self.quantity_dispatched),
			0,
		)

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one stock input is required."))
		for row in self.items:
			if flt(row.requested_qty) <= 0:
				frappe.throw(_("Requested quantity must be greater than zero in row {0}.").format(row.idx))
			if flt(row.approved_qty) < 0 or flt(row.approved_qty) > flt(row.requested_qty):
				frappe.throw(
					_("Approved quantity in row {0} must be between zero and the requested quantity.").format(
						row.idx
					)
				)
			if flt(row.conversion_factor) <= 0:
				frappe.throw(_("UOM Conversion Factor must be greater than zero in row {0}.").format(row.idx))
			if not 0 <= flt(row.recoverable_percent) <= 100:
				frappe.throw(_("Recoverable percentage must be between zero and 100."))

	def validate_material_request_can_cancel(self):
		if not self.material_request or not frappe.db.exists("Material Request", self.material_request):
			return
		docstatus = frappe.db.get_value("Material Request", self.material_request, "docstatus")
		if docstatus == 1:
			frappe.throw(
				_("Cancel the submitted Material Request {0} before cancelling this request.").format(
					frappe.bold(self.material_request)
				)
			)

	def update_fulfillment_status(self):
		issued_by_request_item = {}
		if self.material_request:
			rows = frappe.db.sql(
				"""
				select
					detail.custom_stage_input_request_item,
					coalesce(sum(detail.transfer_qty), 0) as issued_qty
				from `tabStock Entry Detail` detail
				inner join `tabStock Entry` entry on entry.name = detail.parent
				where entry.docstatus = 1
					and detail.material_request = %s
				group by detail.custom_stage_input_request_item
				""",
				self.material_request,
				as_dict=True,
			)
			issued_by_request_item = {
				row.custom_stage_input_request_item: flt(row.issued_qty)
				for row in rows
				if row.custom_stage_input_request_item
			}

		for row in self.items:
			row.issued_stock_qty = issued_by_request_item.get(row.name, 0)
			row.issued_qty = (
				flt(row.issued_stock_qty) / flt(row.conversion_factor)
				if flt(row.conversion_factor)
				else 0
			)
			row.remaining_qty = max(flt(row.approved_qty) - flt(row.issued_qty), 0)
			row.remaining_stock_qty = max(
				flt(row.approved_stock_qty) - flt(row.issued_stock_qty), 0
			)
			frappe.db.set_value(
				row.doctype,
				row.name,
				{
					"issued_qty": row.issued_qty,
					"issued_stock_qty": row.issued_stock_qty,
					"remaining_qty": row.remaining_qty,
					"remaining_stock_qty": row.remaining_stock_qty,
				},
				update_modified=False,
			)

		self.calculate_totals()
		if self.quantity_needed and self.quantity_remaining <= 0:
			status = "Fulfilled"
		elif self.quantity_dispatched > 0:
			status = "Partially Fulfilled"
		else:
			status = "Approved" if self.docstatus == 1 else self.status

		self.db_set(
			{
				"quantity_dispatched": self.quantity_dispatched,
				"quantity_remaining": self.quantity_remaining,
				"status": status,
			},
			update_modified=False,
		)
		return status


@frappe.whitelist()
def create_material_request(input_request):
	doc = frappe.get_doc("Stage Input Request", input_request)
	if doc.docstatus != 1:
		frappe.throw(_("Submit the Stage Input Request before creating a Material Request."))
	return create_material_request_from_input_request(doc)


@frappe.whitelist()
def refresh_fulfillment(input_request):
	return frappe.get_doc("Stage Input Request", input_request).update_fulfillment_status()


@frappe.whitelist()
def get_recipe_input_plan(crop_cycle, stage=None):
	cycle = frappe.get_doc("Crop Cycle", crop_cycle)
	if not cycle.recipe:
		return []
	area_acres = flt(frappe.db.get_value("Farm Plot", cycle.plot, "area_acres"))
	if area_acres <= 0:
		frappe.throw(_("Farm Plot area must be greater than zero."))

	stage_name = (
		frappe.db.get_value("Crop Cycle Stage", stage, "stage_name")
		if stage
		else None
	)
	rows = frappe.get_all(
		"Recipe Input Item",
		filters={
			"parent": cycle.recipe,
			"parenttype": "Crop Recipe",
			"resource_type": "Stock Item",
		},
		fields=[
			"name",
			"item_code",
			"input_name",
			"quantity_per_acre",
			"unit",
			"stock_uom",
			"conversion_factor",
			"recipe_stage",
			"recovery_policy",
			"recoverable_percent",
			"recovery_rate_basis",
			"contract_recovery_rate",
			"source_warehouse",
		],
		order_by="stage_index, idx",
	)
	if stage_name:
		rows = [row for row in rows if row.recipe_stage == stage_name]

	return [
		{
			"recipe_input_item": row.name,
			"item_code": row.item_code,
			"item_name": row.input_name,
			"requested_qty": flt(row.quantity_per_acre) * area_acres,
			"uom": row.unit,
			"conversion_factor": row.conversion_factor,
			"stock_uom": row.stock_uom,
			"source_warehouse": row.source_warehouse,
			"recovery_policy": row.recovery_policy,
			"recoverable_percent": row.recoverable_percent,
			"recovery_rate_basis": row.recovery_rate_basis,
			"contract_recovery_rate": row.contract_recovery_rate,
		}
		for row in rows
		if row.item_code
	]


@frappe.whitelist()
def get_item_uom_details(item_code, uom=None):
	conversion = get_item_uom_conversion(item_code, uom)
	return {
		"uom": conversion.uom,
		"stock_uom": conversion.stock_uom,
		"conversion_factor": conversion.conversion_factor,
	}
