"""Preserve existing parent-seed quantities while enabling prepared snapshots."""

import frappe


def execute():
	if not frappe.db.has_column("Crop Recipe", "parent_seed_preparation_status"):
		return

	# Existing ratio recipes predate the preparation fingerprint. Their stored
	# kg/ha values remain authoritative until a user explicitly reprepares them.
	frappe.db.sql(
		"""
		update `tabCrop Recipe` recipe
		set recipe.parent_seed_preparation_status = case
			when recipe.parent_seed_calculation_method = 'Ratio and Lot Analysis'
			 and exists (
				select 1 from `tabRecipe Parent Seed Item` item
				where item.parent = recipe.name
				  and item.parenttype = 'Crop Recipe'
				  and item.parentfield = 'parent_seed_items'
			 ) then 'Legacy Preserved'
			when recipe.parent_seed_calculation_method = 'Ratio and Lot Analysis'
				then 'Not Prepared'
			else recipe.parent_seed_preparation_status
		end,
		recipe.parent_seed_formula_version = case
			when recipe.parent_seed_calculation_method = 'Ratio and Lot Analysis'
			 and exists (
				select 1 from `tabRecipe Parent Seed Item` item
				where item.parent = recipe.name
				  and item.parenttype = 'Crop Recipe'
				  and item.parentfield = 'parent_seed_items'
			 ) then 'Legacy'
			else recipe.parent_seed_formula_version
		end
		where recipe.parent_seed_preparation_status is null
		   or recipe.parent_seed_preparation_status = ''
		   or recipe.parent_seed_preparation_status = 'Not Prepared'
		"""
	)

	if frappe.db.has_column("Recipe Parent Seed Item", "calculation_formula_version"):
		frappe.db.sql(
			"""
			update `tabRecipe Parent Seed Item` item
			inner join `tabCrop Recipe` recipe on recipe.name = item.parent
			set item.calculation_formula_version = 'Legacy',
				item.allowance_percent_snapshot = recipe.seed_requirement_allowance_percent
			where item.parenttype = 'Crop Recipe'
			  and item.parentfield = 'parent_seed_items'
			  and (item.calculation_formula_version is null or item.calculation_formula_version = '')
			"""
		)
