# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from naseco_fieldopsbackend.fieldops_finance import (
	calculate_crop_cycle_exposure,
)
from naseco_fieldopsbackend.inspection_scheduler import sync_crop_cycle_lifecycle


class CropCycle(Document):
	def before_validate(self):
		self.apply_contract_terms()

	def validate(self):
		self.validate_single_cycle_per_plot()
		self.validate_planting_window()

	def before_save(self):
		"""Auto-update status based on dates"""
		if self.planting_date and not self.production_category:
			frappe.throw("Production Category is required when Planting Date is set.")
		if self.planting_date and not self.start_date:
			self.start_date = self.planting_date
		self.update_status()

	def apply_contract_terms(self):
		if not self.production_contract:
			frappe.throw(
				_("A submitted Outgrower Production Contract is required."),
				title=_("Production Contract Required"),
			)
		contract = frappe.get_doc(
			"Outgrower Production Contract",
			self.production_contract,
		)
		if contract.docstatus != 1 or contract.status not in ("Active", "Fulfilled"):
			frappe.throw(
				_("Production Contract {0} must be submitted and Active.").format(
					frappe.bold(contract.name)
				)
			)
		if contract.linked_crop_cycle and contract.linked_crop_cycle != self.name:
			frappe.throw(
				_("Production Contract {0} is already linked to Crop Cycle {1}.").format(
					frappe.bold(contract.name),
					frappe.bold(contract.linked_crop_cycle),
				)
			)

		contract_fields = {
			"plot": "farm_plot",
			"crop": "crop",
			"variety": "variety",
			"season": "season",
			"recipe": "crop_recipe",
			"company": "company",
			"supplier": "supplier",
			"pricing_policy": "pricing_policy",
			"contracted_area_hectares": "contracted_area_hectares",
			"expected_yield_kg_per_hectare": "expected_yield_kg_per_hectare",
			"contracted_quota_qty": "contracted_quota_qty",
			"harvest_item": "harvest_item",
			"harvest_uom": "harvest_uom",
			"expected_yield_qty": "expected_yield_qty",
			"contract_rate": "contract_rate",
			"currency": "currency",
			"expected_harvest_value": "expected_harvest_value",
			"max_exposure_percent": "max_exposure_percent",
			"production_category": "production_category",
			"start_date": "planting_start_date",
			"expected_harvest_date": "expected_harvest_date",
		}
		for cycle_field, contract_field in contract_fields.items():
			self.set(cycle_field, contract.get(contract_field))

	def validate_planting_window(self):
		if not self.planting_date or not self.production_contract:
			return
		planting_from, planting_to = frappe.db.get_value(
			"Outgrower Production Contract",
			self.production_contract,
			["planting_start_date", "planting_end_date"],
		)
		if (
			planting_from
			and planting_to
			and not getdate(planting_from) <= getdate(self.planting_date) <= getdate(planting_to)
		):
			frappe.throw(
				_("Planting Date must be within the contracted planting window {0} to {1}.").format(
					frappe.format_value(planting_from, {"fieldtype": "Date"}),
					frappe.format_value(planting_to, {"fieldtype": "Date"}),
				)
			)

	def validate_single_cycle_per_plot(self):
		if not self.plot:
			return

		existing_cycle = get_existing_cycle_for_plot(self.plot, self.name)
		if existing_cycle:
			frappe.throw(
				_("Farm Plot {0} is already assigned to Crop Cycle {1}. A plot can have only one Crop Cycle.").format(
					frappe.bold(self.plot),
					frappe.bold(existing_cycle.crop_cycle_id or existing_cycle.name),
				),
				title=_("Crop Cycle Already Exists"),
			)

	def on_update(self):
		"""Generate agronomy and QA schedules once planting starts."""
		if self.production_contract:
			frappe.db.set_value(
				"Outgrower Production Contract",
				self.production_contract,
				"linked_crop_cycle",
				self.name,
				update_modified=False,
			)
			if self.status == "COMPLETED":
				frappe.db.set_value(
					"Outgrower Production Contract",
					self.production_contract,
					"status",
					"Fulfilled",
					update_modified=False,
				)
		sync_crop_cycle_lifecycle(self)

	def on_trash(self):
		if self.production_contract:
			frappe.db.set_value(
				"Outgrower Production Contract",
				self.production_contract,
				"linked_crop_cycle",
				None,
				update_modified=False,
			)

	def update_status(self):
		"""
		Update crop cycle status based on dates:
		- PLANNED: start_date is in the future
		- ACTIVE: started but not harvested
		- COMPLETED: actual_harvest_date is set
		"""
		if self.actual_harvest_date:
			self.status = "COMPLETED"
		elif self.start_date:
			current_date = getdate(now_datetime())
			start_date = getdate(self.start_date)

			if start_date > current_date:
				self.status = "PLANNED"
			else:
				self.status = "ACTIVE"
		else:
			self.status = "PLANNED"


def get_existing_cycle_for_plot(plot, exclude_cycle=None):
	return frappe.db.get_value(
		"Crop Cycle",
		{
			"plot": plot,
			"name": ["!=", exclude_cycle],
		},
		["name", "crop_cycle_id"],
		as_dict=True,
	)


@frappe.whitelist()
def refresh_financial_summary(crop_cycle):
	doc = frappe.get_doc("Crop Cycle", crop_cycle)
	summary = calculate_crop_cycle_exposure(doc.name)
	doc.db_set(
		{
			"recoverable_stock_value": summary.recoverable_stock_value,
			"cash_advanced": summary.cash_advanced,
			"pending_cash_advance": summary.pending_cash_advance,
			"total_exposure": summary.total_exposure,
			"available_advance_capacity": summary.available_advance_capacity,
			"actual_harvest_value": summary.actual_harvest_value,
			"forecast_net_payable": summary.forecast_net_payable,
		},
		update_modified=False,
	)
	return summary
