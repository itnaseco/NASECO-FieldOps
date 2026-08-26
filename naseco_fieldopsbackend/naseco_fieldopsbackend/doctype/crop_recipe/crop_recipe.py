# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime

from naseco_fieldopsbackend.crop_cycle_lifecycle import (
	STAGE_NAMES,
	canonical_stage_name,
	get_stage,
)
from naseco_fieldopsbackend.uom import get_item_uom_conversion


class CropRecipe(Document):
	def before_validate(self):
		self.recipe_version = self.recipe_version or "Legacy-1.0"
		self.effective_from = self.effective_from or self.creation or now_datetime()
		if not self.status:
			self.status = "Active" if self.docstatus == 1 else "Draft"

	def validate(self):
		self.validate_scope_and_dates()
		self.validate_applicable_varieties()
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

		self.validate_parent_seed_items()

	def before_submit(self):
		if self.variety_scope == "All Crop Varieties" and flt(self.expected_yield_kg_per_hectare) <= 0:
			frappe.throw(_("Expected Yield (Kg/Ha) must be greater than zero before submitting the recipe."))
		self.status = "Active"
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
		filters = {"crop": self.crop, "docstatus": 1, "status": "Active", "name": ["!=", self.name]}
		for fieldname in ("outgrower", "company"):
			filters[fieldname] = self.get(fieldname) or ["is", "not set"]
		this_varieties = None if self.variety_scope == "All Crop Varieties" else {row.variety for row in self.applicable_varieties if row.enabled}
		for name in frappe.get_all(self.doctype, filters=filters, pluck="name"):
			other = frappe.get_doc(self.doctype, name)
			other_varieties = None if other.variety_scope == "All Crop Varieties" else {row.variety for row in other.applicable_varieties if row.enabled}
			if this_varieties is None or other_varieties is None or this_varieties & other_varieties:
				frappe.throw(_("An active recipe already exists for an overlapping variety, outgrower and company scope."))

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def validate_scope_and_dates(self):
		if self.variety:
			variety_crop = frappe.db.get_value("Crop Variety", self.variety, "crop")
			if variety_crop and variety_crop != self.crop:
				frappe.throw(_("Crop Variety must belong to the selected Crop."))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))

	def validate_applicable_varieties(self):
		self.variety_scope = self.variety_scope or ("Selected Varieties" if self.variety else "All Crop Varieties")
		seen = set()
		enabled = 0
		for row in self.applicable_varieties or []:
			if row.variety in seen:
				frappe.throw(_("Crop Variety {0} is listed more than once.").format(row.variety))
			seen.add(row.variety)
			if frappe.db.get_value("Crop Variety", row.variety, "crop") != self.crop:
				frappe.throw(_("Applicable Crop Variety {0} must belong to {1}.").format(row.variety, self.crop))
			if row.enabled:
				enabled += 1
				if self.docstatus == 1 and flt(row.expected_yield_kg_per_hectare) <= 0:
					frappe.throw(_("Expected Yield must be positive for enabled variety {0}.").format(row.variety))
		if self.variety_scope == "Selected Varieties" and not enabled:
			frappe.throw(_("Add at least one enabled Applicable Variety."))

	def validate_parent_seed_items(self):
		seen = set()
		for row in self.parent_seed_items or []:
			if row.variety and frappe.db.get_value("Crop Variety", row.variety, "crop") != self.crop:
				frappe.throw(_("Parent seed variety in row {0} must belong to {1}.").format(row.idx, self.crop))
			if row.variety and self.variety_scope == "Selected Varieties" and row.variety not in {item.variety for item in self.applicable_varieties if item.enabled}:
				frappe.throw(_("Parent seed variety in row {0} is not an enabled Applicable Variety.").format(row.idx))
			key = (row.variety, row.ratio_group, row.parent_role, row.item_code)
			if key in seen:
				frappe.throw(_("Parent seed row {0} is duplicated.").format(row.idx))
			seen.add(key)
			row_complete = row.item_code and row.uom and flt(row.ratio_value) > 0 and flt(row.quantity_per_hectare) > 0
			if not row_complete:
				if self.docstatus == 1:
					frappe.throw(_("Complete Seed Item, Ratio Value, Quantity per Hectare and Recipe UOM in parent-seed row {0}.").format(row.idx))
				continue
			item = frappe.db.get_value("Item", row.item_code, ["stock_uom", "is_stock_item", "disabled"], as_dict=True)
			if not item or not item.is_stock_item or item.disabled:
				frappe.throw(_("Parent seed Item {0} must be an enabled stock Item.").format(row.item_code))
			conversion = get_item_uom_conversion(row.item_code, row.uom or item.stock_uom)
			row.uom = conversion.uom
			row.stock_uom = conversion.stock_uom

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
			row.stock_quantity_per_hectare = (
				flt(row.quantity_per_hectare) * flt(row.conversion_factor)
			)
			if not flt(row.quantity_per_hectare) and flt(row.quantity_per_acre):
				row.quantity_per_hectare = flt(row.quantity_per_acre) * 2.47105381467
			if not flt(row.quantity_per_acre) and flt(row.quantity_per_hectare):
				row.quantity_per_acre = flt(row.quantity_per_hectare) * 0.40468564224
			row.stock_quantity_per_hectare = flt(row.quantity_per_hectare) * flt(row.conversion_factor)
			if flt(row.quantity_per_hectare) <= 0:
				frappe.throw(_("Quantity per hectare must be greater than zero for {0}.").format(row.item_code))
			# Float/Percent fields are loaded as 0 for legacy rows that have no
			# override. Only a non-zero value represents an override requiring a
			# reason; zero can still be explicitly selected by supplying a reason.
			if flt(row.markup_percent_override) and not (row.markup_override_reason or "").strip():
				frappe.throw(_("A reason is required for the markup override on {0}.").format(row.item_code))

		if row.recovery_policy == "Fully Recoverable":
			row.recoverable_percent = 100
		elif row.recovery_policy in ("Company Subsidy", "Non-Recoverable"):
			row.recoverable_percent = 0

		if not 0 <= flt(row.recoverable_percent) <= 100:
			frappe.throw(_("Recoverable percentage must be between 0 and 100."))
		if row.recovery_rate_basis == "Contract Rate" and not flt(row.contract_recovery_rate):
			frappe.throw(_("Contract Recovery Rate is required when that rate basis is selected."))


def get_recipe_variety_yield(recipe, variety):
	if recipe.variety_scope == "Selected Varieties":
		for row in recipe.applicable_varieties or []:
			if row.enabled and row.variety == variety:
				return flt(row.expected_yield_kg_per_hectare)
		return None
	return flt(recipe.expected_yield_kg_per_hectare)


@frappe.whitelist()
def get_recipe_target_defaults(recipe_name, variety):
	recipe = frappe.get_doc("Crop Recipe", recipe_name)
	yield_kg_per_hectare = get_recipe_variety_yield(recipe, variety)
	if yield_kg_per_hectare is None:
		frappe.throw(_("Crop Recipe {0} does not apply to Crop Variety {1}.").format(recipe_name, variety))
	return {"crop": recipe.crop, "expected_yield_kg_per_hectare": yield_kg_per_hectare}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def parent_seed_item_query(doctype, txt, searchfield, start, page_len, filters):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	variety = filters.get("variety")
	crop = filters.get("crop") or frappe.db.get_value("Crop Variety", variety, "crop")
	return frappe.db.sql(
		"""select candidates.item_code, candidates.item_name, candidates.parent_variety
		from (
			select item.name as item_code, item.item_name, mapped_variety.name as parent_variety, mapping.is_default
			from `tabItem` item
			inner join `tabCrop Variety Seed Item` mapping
				on mapping.item_code = item.name and mapping.item_purpose = \"Parent Seed\"
			inner join `tabCrop Variety` mapped_variety on mapped_variety.name = mapping.parent
			where mapped_variety.crop = %(crop)s and mapped_variety.can_be_used_as_parent_seed = 1
			  and item.disabled = 0 and item.is_stock_item = 1
			union
			select item.name, item.item_name, parent_variety.name, 0
			from `tabItem` item
			inner join `tabCrop Variety` parent_variety on parent_variety.name = item.name
			where parent_variety.crop = %(crop)s and parent_variety.can_be_used_as_parent_seed = 1
			  and item.disabled = 0 and item.is_stock_item = 1
		) candidates
		where candidates.item_code like %(txt)s or candidates.item_name like %(txt)s
		group by candidates.item_code, candidates.item_name, candidates.parent_variety
		order by max(candidates.is_default) desc, candidates.item_code
		limit %(start)s, %(page_len)s""",
		{"crop": crop, "txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def applicable_recipe_query(doctype, txt, searchfield, start, page_len, filters):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	crop = filters.get("crop")
	variety = filters.get("variety")
	return frappe.db.sql(
		"""select recipe.name, recipe.recipe_name, recipe.recipe_version
		from `tabCrop Recipe` recipe
		where recipe.crop = %(crop)s
		  and (recipe.name like %(txt)s or recipe.recipe_name like %(txt)s)
		  and (
			recipe.variety_scope = \"All Crop Varieties\"
			or exists (
				select 1 from `tabCrop Recipe Variety` applicable
				where applicable.parent = recipe.name and applicable.enabled = 1
				  and applicable.variety = %(variety)s
			)
		  )
		order by recipe.is_default desc, recipe.modified desc
		limit %(start)s, %(page_len)s""",
		{"crop": crop, "variety": variety, "txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
def clone_recipe(source_recipe, recipe_name, recipe_version):
	from naseco_fieldopsbackend.fieldops_finance import require_outgrower_manager

	require_outgrower_manager()
	source = frappe.get_doc("Crop Recipe", source_recipe)
	clone = frappe.copy_doc(source)
	clone.recipe_name = recipe_name
	clone.recipe_id = None
	clone.recipe_version = recipe_version
	clone.status = "Draft"
	clone.based_on_recipe = source.name
	clone.approved_by = None
	clone.approved_on = None
	clone.amended_from = None
	clone.docstatus = 0
	clone.insert()
	return clone.name
