# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from naseco_fieldopsbackend.crop_cycle_lifecycle import (
	STAGE_NAMES,
	canonical_stage_name,
	get_stage,
)
from naseco_fieldopsbackend.uom import get_item_uom_conversion


class CropRecipe(Document):
	def validate(self):
		stage_index = {}
		stage_name_by_row = {}
		seen_stages = set()
		for s in self.stages or []:
			stage = get_stage(s.stage_code or s.stage_name)
			if not stage:
				frappe.throw(
					_("Recipe stage {0} is not an approved crop-cycle stage.").format(
						frappe.bold(s.stage_name or s.stage_code or s.idx)
					)
				)
			if stage.name in seen_stages:
				frappe.throw(_("Crop-cycle stage {0} is duplicated.").format(stage.name))
			seen_stages.add(stage.name)
			s.stage_code = stage.code
			s.stage_name = stage.name
			s.order_index = stage.order
			if s.start_day_offset in (None, ""):
				s.start_day_offset = stage.start_day
			if s.end_day_offset in (None, ""):
				s.end_day_offset = stage.end_day
			if s.end_day_offset < s.start_day_offset:
				frappe.throw(_("Stage {0} has an invalid day window.").format(stage.name))
			s.duration_days = s.end_day_offset - s.start_day_offset + 1
			stage_index[s.stage_name] = s.order_index
			if s.name and s.stage_name:
				stage_name_by_row[s.name] = s.stage_name

		for row in self.inputs or []:
			self.set_input_item_defaults(row)
			# Migrate old rowname link to stage name if needed
			if row.recipe_stage in stage_name_by_row:
				row.recipe_stage = stage_name_by_row.get(row.recipe_stage)

			# Default recipe_stage from input_type if missing
			row.recipe_stage = canonical_stage_name(row.recipe_stage or row.input_type)

			if row.recipe_stage in stage_index:
				row.stage_index = stage_index.get(row.recipe_stage)
			elif row.recipe_stage not in STAGE_NAMES:
				frappe.throw(
					_("Input {0} must be assigned to an approved recipe stage.").format(
						frappe.bold(row.input_name or row.idx)
					)
				)

	def set_input_item_defaults(self, row):
		if row.resource_type == "Stock Item":
			if not row.item_code:
				frappe.throw(
					_("Stock Item is required for stock input {0}.").format(
						frappe.bold(row.input_name or row.idx)
					)
				)
			item = frappe.db.get_value(
				"Item",
				row.item_code,
				["item_name", "stock_uom", "is_stock_item"],
				as_dict=True,
			)
			if not item or not item.is_stock_item:
				frappe.throw(
					_("Item {0} must be an enabled stock Item.").format(
						frappe.bold(row.item_code)
					)
				)
			row.input_name = item.item_name
			conversion = get_item_uom_conversion(row.item_code, row.unit or item.stock_uom)
			row.unit = conversion.uom
			row.stock_uom = conversion.stock_uom
			row.conversion_factor = conversion.conversion_factor
			row.stock_quantity_per_acre = (
				flt(row.quantity_per_acre) * flt(row.conversion_factor)
			)

		if row.recovery_policy == "Fully Recoverable":
			row.recoverable_percent = 100
		elif row.recovery_policy in ("Company Subsidy", "Non-Recoverable"):
			row.recoverable_percent = 0

		if not 0 <= flt(row.recoverable_percent) <= 100:
			frappe.throw(_("Recoverable percentage must be between 0 and 100."))
		if row.recovery_rate_basis == "Contract Rate" and not flt(row.contract_recovery_rate):
			frappe.throw(_("Contract Recovery Rate is required when that rate basis is selected."))
