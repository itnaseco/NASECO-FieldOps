# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class StageInputDispatch(Document):
	def before_validate(self):
		self.set_stock_context()
		self.received_at = self.received_at or now_datetime()
		self.quantity = self.quantity_dispatched
		self.request_id = self.input_request
		self.input_name = self.item_name

	def validate(self):
		if not self.stock_entry_detail:
			frappe.throw(_("Select a submitted Stock Entry item row."))
		maximum_accuracy = flt(
			frappe.db.get_single_value("FieldOps Settings", "maximum_gps_accuracy_m")
			or 20
		)
		accuracy = flt(self.gps_accuracy_meters)
		if accuracy <= 0:
			frappe.throw(_("Capture the delivery GPS location and accuracy."))
		if accuracy > maximum_accuracy:
			frappe.throw(
				_("GPS accuracy must be within {0} m; the captured accuracy is {1} m.").format(
					maximum_accuracy,
					accuracy,
				)
			)

	def set_stock_context(self):
		if not self.stock_entry:
			return
		if frappe.db.get_value("Stock Entry", self.stock_entry, "docstatus") != 1:
			frappe.throw(_("Only a submitted Stock Entry can be acknowledged."))

		row_name = self.stock_entry_detail
		if not row_name:
			rows = frappe.get_all(
				"Stock Entry Detail",
				filters={"parent": self.stock_entry},
				fields=["name"],
				limit=2,
			)
			if len(rows) == 1:
				row_name = rows[0].name
		if not row_name:
			return

		row = frappe.get_doc("Stock Entry Detail", row_name)
		if row.parent != self.stock_entry:
			frappe.throw(_("The selected item row does not belong to this Stock Entry."))
		if not row.custom_stage_input_request_item:
			frappe.throw(_("The Stock Entry item is not linked to a Stage Input Request item."))

		request_item = frappe.get_doc(
			"Stage Input Request Item",
			row.custom_stage_input_request_item,
		)
		request = frappe.get_doc("Stage Input Request", request_item.parent)
		self.stock_entry_detail = row.name
		self.input_request_item = request_item.name
		self.input_request = request.name
		self.crop_cycle = request.crop_cycle
		self.stage = request.stage
		self.item_code = row.item_code
		self.item_name = row.item_name
		self.quantity_dispatched = row.transfer_qty or row.qty
		self.unit = row.stock_uom
		self.valuation_rate = row.valuation_rate or row.basic_rate
		self.base_cost_rate = row.custom_base_cost_rate
		self.markup_percent = row.custom_risk_markup_percent
		self.recovery_rate = row.custom_final_recovery_rate
		self.pricing_policy = row.custom_recovery_pricing_policy
		self.pricing_policy_version = row.custom_pricing_policy_version
		self.recoverable_amount = row.custom_recoverable_amount


@frappe.whitelist()
def get_unacknowledged_stock_rows(stock_entry):
	if frappe.db.get_value("Stock Entry", stock_entry, "docstatus") != 1:
		return []
	acknowledged = set(
		frappe.get_all(
			"Stage Input Dispatch",
			filters={"docstatus": ["!=", 2]},
			pluck="stock_entry_detail",
		)
	)
	rows = frappe.get_all(
		"Stock Entry Detail",
		filters={
			"parent": stock_entry,
			"custom_stage_input_request_item": ["is", "set"],
		},
		fields=["name", "item_code", "item_name", "transfer_qty", "stock_uom"],
	)
	return [row for row in rows if row.name not in acknowledged]


@frappe.whitelist()
def get_stock_row_context(stock_entry_detail):
	row = frappe.get_doc("Stock Entry Detail", stock_entry_detail)
	if frappe.db.get_value("Stock Entry", row.parent, "docstatus") != 1:
		frappe.throw(_("Only a submitted Stock Entry can be acknowledged."))
	if not row.custom_stage_input_request_item:
		frappe.throw(_("The Stock Entry item is not linked to a FieldOps input request."))
	request_item = frappe.get_doc(
		"Stage Input Request Item",
		row.custom_stage_input_request_item,
	)
	request = frappe.get_doc("Stage Input Request", request_item.parent)
	return {
		"input_request": request.name,
		"input_request_item": request_item.name,
		"crop_cycle": request.crop_cycle,
		"stage": request.stage,
		"item_code": row.item_code,
		"item_name": row.item_name,
		"quantity_dispatched": row.transfer_qty or row.qty,
		"unit": row.stock_uom,
		"valuation_rate": row.valuation_rate or row.basic_rate,
		"recoverable_amount": row.custom_recoverable_amount,
	}
