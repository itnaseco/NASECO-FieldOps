import frappe


def execute():
	"""Preserve existing target yields as historical snapshots."""
	if not frappe.db.has_column("Season Production Target", "recipe_yield_kg_per_hectare"):
		return

	frappe.db.sql(
		"""
		update `tabSeason Production Target`
		set recipe_yield_kg_per_hectare = planned_yield_kg_per_hectare,
			yield_source_recipe = crop_recipe
		where crop_recipe is not null and crop_recipe != ''
			and (yield_source_recipe is null or yield_source_recipe = '')
		"""
	)
