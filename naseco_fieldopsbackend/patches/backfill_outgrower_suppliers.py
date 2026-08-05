# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe

from naseco_fieldopsbackend.fieldops_finance import (
	create_or_get_outgrower_supplier,
	ensure_erpnext_custom_fields,
)


def execute():
	ensure_erpnext_custom_fields()

	for outgrower in frappe.get_all(
		"Outgrower",
		filters={"supplier": ["is", "not set"]},
		pluck="name",
	):
		create_or_get_outgrower_supplier(outgrower)
