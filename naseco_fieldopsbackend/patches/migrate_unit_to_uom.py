# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe

from naseco_fieldopsbackend.uom import ensure_fieldops_uoms, normalize_uom


UNIT_FIELDS = (
	("Inspection Attribute", "unit"),
	("Inspection Parameter", "unit"),
	("Inspection Standard", "unit"),
	("Inspection Take Result", "unit"),
	("Inspection Result", "unit"),
	("Recipe Input Item", "unit"),
	("Stage Input Request", "unit"),
	("Stage Input Dispatch", "unit"),
	("Visit Finding", "unit"),
	("Finding", "unit"),
)


def execute():
	"""Migrate the custom Unit master and all FieldOps links to ERPNext UOM."""
	unit_values = _get_unit_values()
	ensure_fieldops_uoms(unit_values)

	for source_value in unit_values:
		target_value = normalize_uom(source_value)
		if not target_value or target_value == source_value:
			continue

		for doctype, fieldname in UNIT_FIELDS:
			if frappe.db.table_exists(doctype) and frappe.db.has_column(doctype, fieldname):
				frappe.db.sql(
					f"UPDATE `tab{doctype}` SET `{fieldname}` = %s WHERE `{fieldname}` = %s",
					(target_value, source_value),
				)

	_replace_workspace_links()
	_remove_custom_unit_doctype()
	frappe.clear_cache()


def _get_unit_values():
	values = set()

	if frappe.db.table_exists("Unit"):
		values.update(frappe.db.sql_list("SELECT name FROM `tabUnit` WHERE IFNULL(name, '') != ''"))

	for doctype, fieldname in UNIT_FIELDS:
		if frappe.db.table_exists(doctype) and frappe.db.has_column(doctype, fieldname):
			values.update(
				frappe.db.sql_list(
					f"SELECT DISTINCT `{fieldname}` FROM `tab{doctype}` "
					f"WHERE IFNULL(`{fieldname}`, '') != ''"
				)
			)

	return sorted(values)


def _replace_workspace_links():
	if frappe.db.table_exists("Workspace Link"):
		frappe.db.sql(
			"""
			UPDATE `tabWorkspace Link`
			SET link_to = 'UOM', label = CASE WHEN label = 'Unit' THEN 'UOM' ELSE label END
			WHERE link_to = 'Unit' AND link_type = 'DocType'
			"""
		)

	if frappe.db.table_exists("Workspace Shortcut"):
		frappe.db.sql(
			"""
			UPDATE `tabWorkspace Shortcut`
			SET link_to = 'UOM', label = CASE WHEN label = 'Unit' THEN 'UOM' ELSE label END
			WHERE link_to = 'Unit' AND type = 'DocType'
			"""
		)


def _remove_custom_unit_doctype():
	if not frappe.db.exists("DocType", "Unit"):
		return

	remaining_links = frappe.get_all(
		"DocField",
		filters={"fieldtype": "Link", "options": "Unit"},
		pluck="parent",
	)
	remaining_links.extend(
		frappe.get_all(
			"Custom Field",
			filters={"fieldtype": "Link", "options": "Unit"},
			pluck="dt",
		)
	)
	if remaining_links:
		frappe.throw(
			"Cannot remove the custom Unit DocType while Link fields still reference it: "
			+ ", ".join(sorted(set(remaining_links)))
		)

	frappe.delete_doc("DocType", "Unit", force=1, ignore_permissions=True)


def drop_legacy_unit_table():
	if frappe.db.exists("DocType", "Unit"):
		frappe.throw("Cannot drop tabUnit while the custom Unit DocType still exists")

	if frappe.db.table_exists("Unit"):
		frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabUnit`")
