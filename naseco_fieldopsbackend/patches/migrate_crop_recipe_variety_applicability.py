import frappe


def execute():
	for name, variety, expected_yield in frappe.get_all(
		"Crop Recipe",
		fields=["name", "variety", "expected_yield_kg_per_hectare"],
		as_list=True,
	):
		scope = "Selected Varieties" if variety else "All Crop Varieties"
		frappe.db.set_value("Crop Recipe", name, "variety_scope", scope, update_modified=False)
		if not variety:
			continue
		if not frappe.db.exists("Crop Recipe Variety", {"parent": name, "variety": variety}):
			frappe.get_doc({
				"doctype": "Crop Recipe Variety",
				"parent": name,
				"parenttype": "Crop Recipe",
				"parentfield": "applicable_varieties",
				"variety": variety,
				"expected_yield_kg_per_hectare": expected_yield,
				"enabled": 1,
			}).db_insert()
		frappe.db.set_value(
			"Recipe Parent Seed Item",
			{"parent": name, "variety": ["is", "not set"]},
			"variety", variety, update_modified=False,
		)
