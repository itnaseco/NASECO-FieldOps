# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, now_datetime, today

from decimal import Decimal, ROUND_HALF_UP

from naseco_fieldopsbackend.crop_cycle_lifecycle import (
	STAGE_NAMES,
	canonical_stage_name,
	get_stage,
)
from naseco_fieldopsbackend.uom import get_item_uom_conversion
from naseco_fieldopsbackend.parent_seed_calculation import calculate_parent_requirement


PARENT_SEED_FORMULA_VERSION = "1.0"
PARENT_SEED_ROLES = ("Female", "Male")


def get_stage_day_number(start_day_offset, end_day_offset):
	"""Return the human-facing milestone day for a recipe stage window."""
	if start_day_offset in (None, "") or end_day_offset in (None, ""):
		return None
	start = int(start_day_offset)
	end = int(end_day_offset)
	if end < start:
		return None
	# Pre-planting windows are described from their earliest configured offset,
	# while non-negative stages use their end milestone. Planting is the
	# operational first day even though its scheduling offset is zero.
	if start < 0:
		days_prior = abs(start)
		return f"{days_prior} {'Day' if days_prior == 1 else 'Days'} Prior"
	return "1" if start == 0 and end == 0 else str(end)


def get_parent_seed_population(recipe, variety):
	for row in recipe.applicable_varieties or []:
		get_value = row.get if hasattr(row, "get") else lambda fieldname: getattr(row, fieldname, None)
		override = flt(get_value("expected_plants_per_hectare_override"))
		if get_value("enabled") and get_value("variety") == variety and override > 0:
			return override
	return flt(recipe.expected_plants_per_hectare)


def get_parent_seed_input_hash(recipe):
	"""Fingerprint only inputs that determine the persisted parent-seed snapshot."""
	applicable = sorted(
		(
			row.variety,
			int(bool(row.enabled)),
			flt(row.expected_plants_per_hectare_override),
		)
		for row in recipe.applicable_varieties or []
	)
	rows = sorted(
		[{
			"variety": row.variety,
			"parentage": row.parentage,
			"parent_role": row.parent_role,
			"parent_variety": row.parent_variety,
			"required_seed_category": row.required_seed_category,
			"required_seed_class": row.required_seed_class,
			"ratio_value": flt(row.ratio_value),
			"calculation_basis": row.calculation_basis,
			"lot_analysis": row.lot_analysis,
			"item_code": row.item_code,
			"germination_percent": flt(row.germination_percent),
			"thousand_kernel_weight_g": flt(row.thousand_kernel_weight_g),
			"assumption_source": row.get("assumption_source"),
			"assumption_reason": row.get("assumption_reason"),
			"recovery_policy": row.recovery_policy,
			"recoverable_percent": flt(row.recoverable_percent),
			"source_warehouse": row.source_warehouse,
		}
		for row in recipe.parent_seed_items or []],
		key=lambda row: (row["variety"] or "", row["parent_role"] or ""),
	)
	payload = {
		"formula_version": PARENT_SEED_FORMULA_VERSION,
		"variety_scope": recipe.variety_scope,
		"expected_plants_per_hectare": flt(recipe.expected_plants_per_hectare),
		"allowance_percent": flt(recipe.seed_requirement_allowance_percent),
		"applicable_varieties": applicable,
		"rows": rows,
	}
	return hashlib.sha256(
		json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
	).hexdigest()


class CropRecipe(Document):
	def before_validate(self):
		self.recipe_version = self.recipe_version or "Legacy-1.0"
		self.effective_from = self.effective_from or self.creation or now_datetime()
		if not self.parent_seed_calculation_method:
			# Missing values identify recipes created before the configurable
			# calculation model. Keep them on their historical behaviour during
			# fixture import, migrations and API updates. Desk explicitly selects
			# Ratio and Lot Analysis for newly-created recipes.
			self.parent_seed_calculation_method = "Legacy Fixed Kg/Ha"
		if not self.status:
			self.status = "Active" if self.docstatus == 1 else "Draft"
		if self.parent_seed_calculation_method == "Ratio and Lot Analysis" and not self.parent_seed_preparation_status:
			self.parent_seed_preparation_status = "Not Prepared"

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
			s.day_number = get_stage_day_number(s.start_day_offset, s.end_day_offset)
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
		self.update_parent_seed_preparation_state()

	def before_submit(self):
		if self.variety_scope == "All Crop Varieties" and flt(self.expected_yield_kg_per_hectare) <= 0:
			frappe.throw(_("Expected Yield (Kg/Ha) must be greater than zero before submitting the recipe."))
		if (
			self.parent_seed_calculation_method == "Ratio and Lot Analysis"
			and self.parent_seed_preparation_status not in ("Prepared", "Legacy Preserved")
		):
			frappe.throw(_("Prepare parent-seed requirements before submitting this Crop Recipe."))
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
		if self.parent_seed_calculation_method == "Ratio and Lot Analysis":
			if self.parent_seed_preparation_status == "Legacy Preserved" and not self.flags.parent_seed_preparation_commit:
				return
			if not self.flags.parent_seed_preparation_commit:
				if self.parent_seed_preparation_status in ("Not Prepared", "Outdated", None, ""):
					return
				current_hash = get_parent_seed_input_hash(self)
				if not self.parent_seed_input_hash or current_hash != self.parent_seed_input_hash:
					self.parent_seed_preparation_status = "Outdated"
					return
			self.validate_ratio_parent_seed_items()
			return

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

	def validate_ratio_parent_seed_items(self):
		if flt(self.expected_plants_per_hectare) <= 0:
			frappe.throw(_("Expected Plants per Hectare must be greater than zero for ratio-based parent seed calculation."))
		if flt(self.seed_requirement_allowance_percent) < 0:
			frappe.throw(_("Operational Seed Allowance cannot be negative."))
		if self.variety_scope != "Selected Varieties":
			frappe.throw(_("Ratio-based parent seed calculation requires Selected Varieties so every output variety has explicit parents."))

		enabled_varieties = {row.variety for row in self.applicable_varieties or [] if row.enabled}
		rows_by_variety = {variety: [] for variety in enabled_varieties}
		for row in self.parent_seed_items or []:
			if row.variety not in enabled_varieties:
				frappe.throw(_("Parent seed row {0} must reference an enabled Applicable Variety.").format(row.idx))
			if row.parent_role not in ("Female", "Male"):
				frappe.throw(_("Ratio-based recipe row {0} must use Female or Male as Parent Role.").format(row.idx))
			if not row.parentage or not row.parent_variety or not row.required_seed_category:
				frappe.throw(_("Complete Parentage, Parent Variety and Required Seed Category in row {0}.").format(row.idx))
			if flt(row.ratio_value) <= 0 or flt(row.ratio_value) != int(flt(row.ratio_value)):
				frappe.throw(_("Ratio Value in row {0} must be a positive whole number.").format(row.idx))
			parentage = frappe.get_doc("Seed Variety Parentage", row.parentage)
			if parentage.docstatus != 1 or parentage.status != "Active" or parentage.output_variety != row.variety:
				frappe.throw(_("Parentage {0} must be active and belong to output variety {1}.").format(row.parentage, row.variety))
			match = next((p for p in parentage.parents if p.parent_role == row.parent_role), None)
			if not match or match.parent_variety != row.parent_variety:
				frappe.throw(_("The {0} parent in row {1} does not match parentage {2}.").format(row.parent_role, row.idx, row.parentage))
			if match.required_seed_category != row.required_seed_category or (match.required_seed_class or None) != (row.required_seed_class or None):
				frappe.throw(_("Seed category or class in row {0} does not match its parentage.").format(row.idx))
			rows_by_variety[row.variety].append(row)

		for variety, rows in rows_by_variety.items():
			roles = [row.parent_role for row in rows]
			if sorted(roles) != ["Female", "Male"]:
				frappe.throw(_("Output variety {0} must have exactly one Female and one Male ratio row.").format(variety))
			total_ratio = sum(Decimal(str(row.ratio_value)) for row in rows)
			for row in rows:
				share = Decimal(str(row.ratio_value)) / total_ratio
				row.population_percent = float((share * Decimal("100")).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
				target_population = get_parent_seed_population(self, variety)
				if target_population <= 0:
					frappe.throw(_("Expected Plants per Hectare must be greater than zero for output variety {0}.").format(variety))
				row.expected_plants_per_hectare = float((Decimal(str(target_population)) * share).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
				self.apply_parent_seed_calculation_basis(row, total_ratio)

	def apply_parent_seed_calculation_basis(self, row, total_ratio):
		basis = row.calculation_basis or "Recipe Planning Assumption"
		row.calculation_basis = basis
		if basis == "Approved Lot Analysis":
			if not row.lot_analysis:
				frappe.throw(_("Select an approved Parent Seed Lot Analysis in row {0}.").format(row.idx))
			analysis = frappe.get_doc("Parent Seed Lot Analysis", row.lot_analysis)
			if analysis.docstatus != 1 or analysis.status != "Approved":
				frappe.throw(_("Parent Seed Lot Analysis {0} must be approved.").format(analysis.name))
			if analysis.valid_until and getdate(analysis.valid_until) < getdate(today()):
				frappe.throw(_("Parent Seed Lot Analysis {0} expired on {1}.").format(analysis.name, analysis.valid_until))
			if analysis.parent_variety != row.parent_variety:
				frappe.throw(_("Lot Analysis {0} does not match parent variety {1}.").format(analysis.name, row.parent_variety))
			if (analysis.seed_category or None) != (row.required_seed_category or None) or (analysis.seed_class or None) != (row.required_seed_class or None):
				frappe.throw(_("Lot Analysis {0} does not match the required seed category and class in row {1}.").format(analysis.name, row.idx))
			row.item_code = analysis.item_code
			row.batch_no = analysis.batch_no
			row.germination_percent = analysis.germination_percent
			row.thousand_kernel_weight_g = analysis.thousand_kernel_weight_g
			row.analysis_test_date = analysis.test_date
			row.analysis_valid_until = analysis.valid_until
		else:
			if basis != "Recipe Planning Assumption":
				frappe.throw(_("Invalid parent-seed calculation basis in row {0}.").format(row.idx))
			row.lot_analysis = None
			row.batch_no = None
			row.analysis_test_date = None
			row.analysis_valid_until = None
			if not (row.get("assumption_source") or "").strip():
				frappe.throw(_("Assumption Source is required in parent-seed row {0}.").format(row.idx))

		if not 0 < flt(row.germination_percent) <= 100:
			frappe.throw(_("Germination percentage in row {0} must be greater than zero and at most 100.").format(row.idx))
		if flt(row.thousand_kernel_weight_g) <= 0:
			frappe.throw(_("Thousand-kernel weight in row {0} must be greater than zero.").format(row.idx))
		if not row.item_code:
			frappe.throw(_("Select the parent seed Item in row {0}.").format(row.idx))

		try:
			result = calculate_parent_requirement(
				total_plants_per_hectare=get_parent_seed_population(self, row.variety),
				parent_ratio=row.ratio_value,
				total_ratio=total_ratio,
				germination_percent=row.germination_percent,
				thousand_kernel_weight_g=row.thousand_kernel_weight_g,
				allowance_percent=self.seed_requirement_allowance_percent,
			)
		except ValueError as exc:
			frappe.throw(str(exc))
		row.quantity_per_hectare = float(result["planned_kg_per_hectare"])
		row.required_kernels_per_hectare = float(result["required_kernels_per_hectare"])
		row.base_quantity_per_hectare = float(result["base_kg_per_hectare"])
		row.allowance_percent_snapshot = flt(self.seed_requirement_allowance_percent)
		row.calculation_formula_version = PARENT_SEED_FORMULA_VERSION
		row.uom = frappe.db.get_value("Item", row.item_code, "stock_uom")
		row.stock_uom = row.uom

	def update_parent_seed_preparation_state(self):
		if self.parent_seed_calculation_method != "Ratio and Lot Analysis":
			return
		if self.flags.parent_seed_preparation_commit:
			self.parent_seed_preparation_status = "Prepared"
			self.parent_seed_formula_version = PARENT_SEED_FORMULA_VERSION
			self.parent_seed_input_hash = get_parent_seed_input_hash(self)
			self.parent_seed_prepared_by = frappe.session.user
			self.parent_seed_prepared_on = now_datetime()

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
	parent_variety = filters.get("parent_variety")
	seed_category = filters.get("seed_category")
	seed_class = filters.get("seed_class")
	crop = filters.get("crop") or frappe.db.get_value("Crop Variety", parent_variety or variety, "crop")
	return frappe.db.sql(
		"""select candidates.item_code, candidates.item_name, candidates.parent_variety
		from (
			select item.name as item_code, item.item_name, mapped_variety.name as parent_variety, mapping.is_default
			from `tabItem` item
			inner join `tabCrop Variety Seed Item` mapping
				on mapping.item_code = item.name and mapping.item_purpose = \"Parent Seed\"
			inner join `tabCrop Variety` mapped_variety on mapped_variety.name = mapping.parent
			where mapped_variety.crop = %(crop)s and mapped_variety.can_be_used_as_parent_seed = 1
			  and (%(parent_variety)s is null or mapped_variety.name = %(parent_variety)s)
			  and (%(seed_category)s is null or mapping.seed_category = %(seed_category)s)
			  and (%(seed_class)s is null or mapping.seed_class = %(seed_class)s)
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
		{"crop": crop, "parent_variety": parent_variety, "seed_category": seed_category,
		 "seed_class": seed_class, "txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


def _active_parentage_for_variety(variety, reference_date=None):
	reference_date = getdate(reference_date or today())
	candidates = frappe.get_all(
		"Seed Variety Parentage",
		filters={"output_variety": variety, "docstatus": 1, "status": "Active"},
		fields=["name", "version", "effective_from", "effective_to"],
	)
	eligible = [
		row for row in candidates
		if (not row.effective_from or getdate(row.effective_from) <= reference_date)
		and (not row.effective_to or getdate(row.effective_to) >= reference_date)
	]
	if not eligible:
		frappe.throw(_("No active Seed Variety Parentage is effective for {0}.").format(variety))
	eligible.sort(
		key=lambda row: (getdate(row.effective_from or "1900-01-01"), int(row.version or 0), row.name),
		reverse=True,
	)
	return frappe.get_doc("Seed Variety Parentage", eligible[0].name)


def select_parent_seed_item_mapping(mappings, requested_item=None):
	"""Choose deterministically without treating database order as a business rule."""
	mappings = [frappe._dict(row) for row in mappings or []]
	if requested_item:
		if not any(row.item_code == requested_item for row in mappings):
			frappe.throw(_("Item {0} is not a compatible Parent Seed mapping.").format(requested_item))
		return requested_item, "Existing or Manual Selection"
	defaults = [row for row in mappings if row.is_default]
	if len(defaults) == 1:
		return defaults[0].item_code, "Default Crop Variety Mapping"
	if len(mappings) == 1:
		return mappings[0].item_code, "Unique Crop Variety Mapping"
	return None, "Selection Required"


def _resolve_parent_seed_item(
	parent_variety, seed_category, seed_class, requested_item=None, strict_requested=True
):
	conditions = [
		"mapping.parent = %(parent_variety)s",
		"mapping.parenttype = 'Crop Variety'",
		"mapping.parentfield = 'seed_items'",
		"mapping.item_purpose = 'Parent Seed'",
		"mapping.seed_category = %(seed_category)s",
		"item.disabled = 0",
		"item.is_stock_item = 1",
	]
	if seed_class:
		conditions.append("mapping.seed_class = %(seed_class)s")
	mappings = frappe.db.sql(
		f"""
		select mapping.item_code, mapping.is_default
		from `tabCrop Variety Seed Item` mapping
		inner join `tabItem` item on item.name = mapping.item_code
		where {' and '.join(conditions)}
		order by mapping.is_default desc, mapping.item_code
		""",
		{
			"parent_variety": parent_variety,
			"seed_category": seed_category,
			"seed_class": seed_class,
		},
		as_dict=True,
	)
	if requested_item and not any(row.item_code == requested_item for row in mappings):
		if strict_requested:
			frappe.throw(_("Item {0} is not a compatible Parent Seed mapping.").format(requested_item))
		requested_item = None
	item_code, source = select_parent_seed_item_mapping(mappings, requested_item)
	return item_code, source, mappings


def _preparation_context(recipe):
	if recipe.docstatus != 0:
		frappe.throw(_("Parent-seed requirements can only be prepared on a Draft Crop Recipe."))
	if recipe.variety_scope != "Selected Varieties":
		frappe.throw(_("Parent-seed preparation requires Selected Varieties."))
	existing = {
		(row.variety, row.parent_role): row
		for row in recipe.parent_seed_items or []
	}
	rows = []
	for applicable in recipe.applicable_varieties or []:
		if not applicable.enabled or not applicable.variety:
			continue
		parentage = _active_parentage_for_variety(applicable.variety, recipe.effective_from)
		parents = {row.parent_role: row for row in parentage.parents or [] if row.parent_role in PARENT_SEED_ROLES}
		if sorted(parents) != sorted(PARENT_SEED_ROLES):
			frappe.throw(_("Parentage {0} must contain exactly one Female and one Male parent.").format(parentage.name))
		for role in PARENT_SEED_ROLES:
			definition = parents[role]
			current = existing.get((applicable.variety, role))
			basis = current.calculation_basis if current and current.calculation_basis else "Recipe Planning Assumption"
			current_item = current.item_code if current else None
			item_code = current_item
			item_selection_source = current.get("item_selection_source") if current else None
			if basis == "Recipe Planning Assumption":
				item_code, item_selection_source, _ = _resolve_parent_seed_item(
					definition.parent_variety,
					definition.required_seed_category,
					definition.required_seed_class,
					current_item,
					strict_requested=False,
				)
			elif basis == "Approved Lot Analysis":
				item_selection_source = "Approved Lot Analysis"
			rows.append({
				"variety": applicable.variety,
				"parentage": parentage.name,
				"parent_role": role,
				"parent_variety": definition.parent_variety,
				"required_seed_category": definition.required_seed_category,
				"required_seed_class": definition.required_seed_class,
				"ratio_value": flt(current.ratio_value) if current else (4 if role == "Female" else 1),
				"calculation_basis": basis,
				"lot_analysis": current.lot_analysis if current else None,
				"item_code": item_code,
				"item_selection_source": item_selection_source,
				"germination_percent": flt(current.germination_percent) if current else None,
				"thousand_kernel_weight_g": flt(current.thousand_kernel_weight_g) if current else None,
				"assumption_source": current.get("assumption_source") if current else None,
				"assumption_reason": current.get("assumption_reason") if current else None,
				"recovery_policy": current.recovery_policy if current else "Fully Recoverable",
				"recoverable_percent": flt(current.recoverable_percent) if current else 100,
				"source_warehouse": current.source_warehouse if current else None,
			})
	return {
		"modified": str(recipe.modified),
		"parent_seed_calculation_method": "Ratio and Lot Analysis",
		"expected_plants_per_hectare": flt(recipe.expected_plants_per_hectare),
		"seed_requirement_allowance_percent": flt(recipe.seed_requirement_allowance_percent),
		"variety_populations": {
			row.variety: flt(row.expected_plants_per_hectare_override)
			for row in recipe.applicable_varieties or [] if row.enabled
		},
		"rows": rows,
	}


@frappe.whitelist()
def get_parent_seed_preparation_context(recipe_name):
	recipe = frappe.get_doc("Crop Recipe", recipe_name)
	recipe.check_permission("write")
	return _preparation_context(recipe)


def _parse_preparation_payload(value):
	return frappe.parse_json(value) if isinstance(value, str) else (value or {})


def _validate_parent_seed_item_mapping(parent_variety, item_code, seed_category, seed_class):
	filters = {
		"parent": parent_variety,
		"parenttype": "Crop Variety",
		"parentfield": "seed_items",
		"item_purpose": "Parent Seed",
		"item_code": item_code,
		"seed_category": seed_category,
	}
	if seed_class:
		filters["seed_class"] = seed_class
	if not frappe.db.exists("Crop Variety Seed Item", filters):
		frappe.throw(_("Item {0} is not mapped as compatible Parent Seed for {1}.").format(item_code, parent_variety))


def _build_parent_seed_preview(recipe, settings, requested_rows):
	context = _preparation_context(recipe)
	calculation_method = settings.get("parent_seed_calculation_method") or "Ratio and Lot Analysis"
	if calculation_method != "Ratio and Lot Analysis":
		frappe.throw(_("The preparation wizard creates ratio-based parent-seed snapshots. Legacy fixed quantities must remain on their existing recipe version."))
	context_rows = {(row["variety"], row["parent_role"]): row for row in context["rows"]}
	requested = {
		(row.get("variety"), row.get("parent_role")): frappe._dict(row)
		for row in requested_rows
	}
	if set(requested) != set(context_rows):
		frappe.throw(_("Parent-seed preparation rows no longer match the recipe varieties and active parentages. Reload and try again."))
	default_population = flt(settings.get("expected_plants_per_hectare"))
	allowance = flt(settings.get("seed_requirement_allowance_percent"))
	if default_population <= 0:
		frappe.throw(_("Expected Plants per Hectare must be greater than zero."))
	if allowance < 0:
		frappe.throw(_("Operational Seed Allowance cannot be negative."))
	variety_populations = settings.get("variety_populations") or {}
	warnings = []
	prepared = []
	for variety in sorted({key[0] for key in context_rows}):
		population = flt(variety_populations.get(variety)) or default_population
		if population <= 0:
			frappe.throw(_("Expected Plants per Hectare must be greater than zero for {0}.").format(variety))
		variety_rows = [requested[(variety, role)] for role in PARENT_SEED_ROLES]
		total_ratio = sum(Decimal(str(row.ratio_value or 0)) for row in variety_rows)
		if total_ratio <= 0:
			frappe.throw(_("Female and Male ratios must be greater than zero for {0}.").format(variety))
		for request_row in variety_rows:
			definition = context_rows[(variety, request_row.parent_role)]
			ratio = Decimal(str(request_row.ratio_value or 0))
			if ratio <= 0 or ratio != ratio.to_integral_value():
				frappe.throw(_("Ratio for {0} {1} must be a positive whole number.").format(variety, request_row.parent_role))
			basis = request_row.calculation_basis or "Recipe Planning Assumption"
			lot_analysis = None
			batch_no = None
			test_date = None
			valid_until = None
			assumption_source = None
			assumption_reason = None
			if basis == "Approved Lot Analysis":
				if not request_row.lot_analysis:
					frappe.throw(_("Select an approved lot analysis for {0} {1}.").format(variety, request_row.parent_role))
				analysis = frappe.get_doc("Parent Seed Lot Analysis", request_row.lot_analysis)
				if analysis.docstatus != 1 or analysis.status != "Approved":
					frappe.throw(_("Parent Seed Lot Analysis {0} must be approved.").format(analysis.name))
				if analysis.parent_variety != definition["parent_variety"]:
					frappe.throw(_("Lot Analysis {0} does not match parent variety {1}.").format(analysis.name, definition["parent_variety"]))
				if (analysis.seed_category or None) != (definition["required_seed_category"] or None) or (analysis.seed_class or None) != (definition["required_seed_class"] or None):
					frappe.throw(_("Lot Analysis {0} does not match the required seed category and class.").format(analysis.name))
				if analysis.valid_until and getdate(analysis.valid_until) < getdate(today()):
					frappe.throw(_("Parent Seed Lot Analysis {0} expired on {1}.").format(analysis.name, analysis.valid_until))
				if analysis.valid_until and getdate(analysis.valid_until) <= getdate(add_days(today(), 30)):
					warnings.append(_("Lot Analysis {0} expires on {1}.").format(analysis.name, analysis.valid_until))
				item_code = analysis.item_code
				item_selection_source = "Approved Lot Analysis"
				germination = flt(analysis.germination_percent)
				kernel_weight = flt(analysis.thousand_kernel_weight_g)
				lot_analysis = analysis.name
				batch_no = analysis.batch_no
				test_date = analysis.test_date
				valid_until = analysis.valid_until
			else:
				if basis != "Recipe Planning Assumption":
					frappe.throw(_("Invalid calculation basis for {0} {1}.").format(variety, request_row.parent_role))
				item_code, item_selection_source, compatible_mappings = _resolve_parent_seed_item(
					definition["parent_variety"],
					definition["required_seed_category"],
					definition["required_seed_class"],
					request_row.item_code,
				)
				germination = flt(request_row.germination_percent)
				kernel_weight = flt(request_row.thousand_kernel_weight_g)
				assumption_source = (request_row.assumption_source or "").strip()
				assumption_reason = (request_row.assumption_reason or "").strip()
				if not assumption_source:
					frappe.throw(_("Assumption Source is required for {0} {1}.").format(variety, request_row.parent_role))
				if not item_code and len(compatible_mappings) > 1:
					frappe.throw(_("Multiple compatible Parent Seed Items exist for {0} {1}. Select one explicitly or configure exactly one default Item on parent variety {2}.").format(variety, request_row.parent_role, definition["parent_variety"]))
				warnings.append(_("{0} {1} uses a planning assumption rather than an approved physical lot analysis.").format(variety, request_row.parent_role))
			if not item_code:
				frappe.throw(_("Select the Parent Seed Item for {0} {1}.").format(variety, request_row.parent_role))
			_validate_parent_seed_item_mapping(
				definition["parent_variety"], item_code,
				definition["required_seed_category"], definition["required_seed_class"],
			)
			item = frappe.db.get_value("Item", item_code, ["stock_uom", "is_stock_item", "disabled"], as_dict=True)
			if not item or not item.is_stock_item or item.disabled:
				frappe.throw(_("Parent seed Item {0} must be an enabled stock Item.").format(item_code))
			try:
				calculation = calculate_parent_requirement(
					total_plants_per_hectare=population,
					parent_ratio=ratio,
					total_ratio=total_ratio,
					germination_percent=germination,
					thousand_kernel_weight_g=kernel_weight,
					allowance_percent=allowance,
				)
			except ValueError as exc:
				frappe.throw(str(exc))
			prepared.append({
				**definition,
				"ratio_group": "Primary",
				"ratio_value": float(ratio),
				"population_percent": float(calculation["population_percent"]),
				"expected_plants_per_hectare": float(calculation["expected_plants_per_hectare"]),
				"calculation_basis": basis,
				"lot_analysis": lot_analysis,
				"item_code": item_code,
				"item_selection_source": item_selection_source,
				"germination_percent": germination,
				"thousand_kernel_weight_g": kernel_weight,
				"assumption_source": assumption_source,
				"assumption_reason": assumption_reason,
				"batch_no": batch_no,
				"analysis_test_date": test_date,
				"analysis_valid_until": valid_until,
				"required_kernels_per_hectare": float(calculation["required_kernels_per_hectare"]),
				"base_quantity_per_hectare": float(calculation["base_kg_per_hectare"]),
				"allowance_percent_snapshot": allowance,
				"calculation_formula_version": PARENT_SEED_FORMULA_VERSION,
				"quantity_per_hectare": float(calculation["planned_kg_per_hectare"]),
				"uom": item.stock_uom,
				"stock_uom": item.stock_uom,
				"recovery_policy": request_row.recovery_policy or "Fully Recoverable",
				"recoverable_percent": flt(request_row.recoverable_percent) if request_row.recoverable_percent is not None else 100,
				"source_warehouse": request_row.source_warehouse,
			})
	return {
		"settings": {
			"parent_seed_calculation_method": calculation_method,
			"expected_plants_per_hectare": default_population,
			"seed_requirement_allowance_percent": allowance,
			"variety_populations": variety_populations,
		},
		"rows": prepared,
		"warnings": sorted(set(warnings)),
		"formula_version": PARENT_SEED_FORMULA_VERSION,
	}


@frappe.whitelist()
def preview_parent_seed_preparation(recipe_name, settings, rows):
	recipe = frappe.get_doc("Crop Recipe", recipe_name)
	recipe.check_permission("write")
	return _build_parent_seed_preview(
		recipe,
		_parse_preparation_payload(settings),
		_parse_preparation_payload(rows),
	)


@frappe.whitelist()
def commit_parent_seed_preparation(recipe_name, expected_modified, settings, rows):
	recipe = frappe.get_doc("Crop Recipe", recipe_name)
	recipe.check_permission("write")
	if str(recipe.modified) != str(expected_modified):
		frappe.throw(_("This Crop Recipe changed after the preparation wizard opened. Reload and try again."))
	preview = _build_parent_seed_preview(
		recipe,
		_parse_preparation_payload(settings),
		_parse_preparation_payload(rows),
	)
	recipe.parent_seed_calculation_method = preview["settings"]["parent_seed_calculation_method"]
	recipe.expected_plants_per_hectare = preview["settings"]["expected_plants_per_hectare"]
	recipe.seed_requirement_allowance_percent = preview["settings"]["seed_requirement_allowance_percent"]
	population_overrides = preview["settings"]["variety_populations"]
	for applicable in recipe.applicable_varieties or []:
		applicable.expected_plants_per_hectare_override = flt(population_overrides.get(applicable.variety)) or 0
	recipe.set("parent_seed_items", [])
	for row in preview["rows"]:
		recipe.append("parent_seed_items", row)
	recipe.flags.parent_seed_preparation_commit = True
	recipe.save()
	return {
		"name": recipe.name,
		"modified": str(recipe.modified),
		"status": recipe.parent_seed_preparation_status,
		"rows": [row.as_dict() for row in recipe.parent_seed_items],
		"warnings": preview["warnings"],
	}


@frappe.whitelist()
def get_parentage_parent(parentage, parent_role):
	doc = frappe.get_doc("Seed Variety Parentage", parentage)
	if doc.docstatus != 1 or doc.status != "Active":
		frappe.throw(_("Select an active submitted Seed Variety Parentage."))
	row = next((item for item in doc.parents if item.parent_role == parent_role), None)
	if not row:
		frappe.throw(_("Parentage {0} does not define role {1}.").format(parentage, parent_role))
	return {
		"output_variety": doc.output_variety,
		"parent_variety": row.parent_variety,
		"required_seed_category": row.required_seed_category,
		"required_seed_class": row.required_seed_class,
	}


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
	if clone.parent_seed_calculation_method == "Ratio and Lot Analysis":
		clone.parent_seed_preparation_status = "Outdated"
		clone.parent_seed_input_hash = None
		clone.parent_seed_prepared_by = None
		clone.parent_seed_prepared_on = None
	clone.amended_from = None
	clone.docstatus = 0
	clone.insert()
	return clone.name
