# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class StageInputDispatch(Document):
	def before_validate(self):
		self.dispatched_by = self.dispatched_by or frappe.session.user
		self.external_id = self.external_id or self.dispatch_id
		self.field_visit = self._resolve_visit(self.field_visit)
		if self.stock_entry:
			self.set_stock_context()
		else:
			self.set_request_context()
		self.received_at = self.received_at or now_datetime()
		self.quantity_dispatched = self.quantity_dispatched or self.quantity
		self.quantity = self.quantity_dispatched
		self.request_id = self.input_request
		self.input_name = self.item_name
		self.workflow_status = self.workflow_status or "Pending Stock Posting"

	def validate(self):
		self.validate_mobile_scope()
		if flt(self.quantity_dispatched) <= 0:
			frappe.throw(_("Dispatch quantity must be greater than zero."))
		item = frappe.get_doc("Stage Input Request Item", self.input_request_item)
		pending = frappe.db.sql(
			"""
			select coalesce(sum(quantity_dispatched), 0)
			  from `tabStage Input Dispatch`
			 where input_request_item = %s
			   and name != %s
			   and coalesce(workflow_status, '') not in ('Cancelled', 'Stock Posted')
			""",
			(self.input_request_item, self.name or ""),
		)[0][0]
		remaining = flt(item.approved_qty) - flt(item.issued_qty) - flt(pending)
		if flt(self.quantity_dispatched) > remaining:
			frappe.throw(
				_("Dispatch quantity exceeds the approved remaining quantity of {0} {1}.").format(
					remaining, item.uom or self.unit or ""
				)
			)

	def after_insert(self):
		if not self.stock_entry:
			self.create_draft_stock_entry()

	def _resolve_visit(self, visit):
		if not visit or frappe.db.exists("Field Visit", visit):
			return visit
		return frappe.db.get_value(
			"Field Visit", {"external_id": visit, "visited_by": frappe.session.user}, "name"
		) or frappe.db.get_value(
			"Field Visit", {"visit_id": visit, "visited_by": frappe.session.user}, "name"
		) or visit

	def set_request_context(self):
		self.input_request = self.input_request or self.request_id
		if not self.input_request:
			frappe.throw(_("Select an approved Stage Input Request."))
		if not frappe.db.exists("Stage Input Request", self.input_request):
			self.input_request = frappe.db.get_value(
				"Stage Input Request", "request_id", self.input_request, "name"
			)
		if not self.input_request:
			frappe.throw(_("The selected Stage Input Request was not found."))
		request = frappe.get_doc("Stage Input Request", self.input_request)
		if request.docstatus != 1 or request.status not in (
			"Approved", "Partially Fulfilled", "Partially-Dispatched", "Partially-Fulfilled"
		):
			frappe.throw(_("Only an approved Stage Input Request can be dispatched."))
		candidates = [row for row in request.items if flt(row.remaining_qty) > 0]
		if self.input_request_item:
			candidates = [row for row in candidates if row.name == self.input_request_item]
		elif self.item_code:
			candidates = [row for row in candidates if row.item_code == self.item_code]
		elif self.input_type:
			needle = self.input_type.strip().lower()
			candidates = [row for row in candidates if
				(row.item_name or "").strip().lower() == needle or
				(row.item_code or "").strip().lower() == needle]
		if len(candidates) != 1:
			frappe.throw(_("The selected stage input does not identify one approved request item."))
		item = candidates[0]
		self.input_request_item = item.name
		self.crop_cycle = request.crop_cycle
		self.stage = request.stage
		self.item_code = item.item_code
		self.item_name = item.item_name
		self.input_type = item.item_name
		self.unit = item.uom

	def validate_mobile_scope(self):
		visit = frappe.get_doc("Field Visit", self.field_visit)
		if visit.visited_by != frappe.session.user:
			frappe.throw(_("The Field Visit is not assigned to the logged-in user."), frappe.PermissionError)
		if visit.status not in ("in_progress", "ongoing", "completed"):
			frappe.throw(_("Start the Field Visit before dispatching inputs."))
		if visit.crop_cycle != self.crop_cycle or visit.stage != self.stage:
			frappe.throw(_("The dispatch does not match the Field Visit crop cycle and stage."))
		current_stage = frappe.db.get_value("Crop Cycle", self.crop_cycle, "current_stage")
		if current_stage and current_stage != self.stage:
			frappe.throw(_("Inputs can only be dispatched for the current crop-cycle stage."))

	def create_draft_stock_entry(self):
		request = frappe.get_doc("Stage Input Request", self.input_request)
		if not request.material_request:
			frappe.throw(_("The approved input request has no Material Request."))
		if frappe.db.get_value("Material Request", request.material_request, "docstatus") != 1:
			frappe.throw(_("Submit the linked Material Request before dispatching inputs."))
		from erpnext.stock.doctype.material_request.material_request import make_stock_entry
		entry = make_stock_entry(request.material_request)
		matching = []
		for row in list(entry.items):
			request_item = frappe.db.get_value(
				"Material Request Item", row.material_request_item,
				"custom_stage_input_request_item"
			)
			if request_item == self.input_request_item:
				matching.append(row)
		entry.set("items", matching)
		if len(entry.items) != 1:
			frappe.throw(_("Could not resolve the selected input in the linked Material Request."))
		row = entry.items[0]
		row.qty = flt(self.quantity_dispatched)
		row.transfer_qty = flt(self.quantity_dispatched) * flt(row.conversion_factor or 1)
		entry.insert(ignore_permissions=True)
		self.db_set({
			"stock_entry": entry.name,
			"stock_entry_detail": entry.items[0].name,
			"workflow_status": "Pending Stores Approval",
		}, update_modified=False)

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
