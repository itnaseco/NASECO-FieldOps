# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Keep every pre-existing recipe on its approved fixed kg/ha behaviour."""
	if not frappe.db.has_column("Crop Recipe", "parent_seed_calculation_method"):
		return
	frappe.db.sql(
		"""update `tabCrop Recipe`
		set parent_seed_calculation_method='Legacy Fixed Kg/Ha'
		where coalesce(parent_seed_calculation_method, '')=''"""
	)
