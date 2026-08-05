# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe

from naseco_fieldopsbackend.roles import (
	FIELDOPS_FINANCE_APPROVER_ROLE,
	FIELDOPS_STORES_USER_ROLE,
	OUTGROWER_MANAGER_ROLE,
	OUTGROWER_SUPERVISOR_ROLE,
	QUALITY_INSPECTOR_ROLE,
	QUALITY_MANAGER_ROLE,
)


def _roles(user):
	return set(frappe.get_roles(user))


def _has_management_scope(user):
	roles = _roles(user)
	return (
		user == "Administrator"
		or "System Manager" in roles
		or OUTGROWER_MANAGER_ROLE in roles
		or QUALITY_MANAGER_ROLE in roles
		or FIELDOPS_FINANCE_APPROVER_ROLE in roles
		or FIELDOPS_STORES_USER_ROLE in roles
	)


def get_permission_query_conditions(user=None, doctype=None):
	user = user or frappe.session.user
	if _has_management_scope(user):
		return ""

	roles = _roles(user)
	user_sql = frappe.db.escape(user)
	if OUTGROWER_SUPERVISOR_ROLE in roles:
		conditions = {
			"Outgrower": f"`tabOutgrower`.assigned_supervisor = {user_sql}",
			"Farm Plot": (
				"exists (select 1 from `tabOutgrower` og "
				"where og.name = `tabFarm Plot`.outgrower "
				f"and og.assigned_supervisor = {user_sql})"
			),
			"Crop Cycle": (
				"exists (select 1 from `tabFarm Plot` plot "
				"inner join `tabOutgrower` og on og.name = plot.outgrower "
				"where plot.name = `tabCrop Cycle`.plot "
				f"and og.assigned_supervisor = {user_sql})"
			),
			"Stage Activity": f"`tabStage Activity`.assigned_to = {user_sql}",
			"Agronomy Report": f"`tabAgronomy Report`.assigned_supervisor = {user_sql}",
			"Field Corrective Action": (
				f"`tabField Corrective Action`.assigned_to = {user_sql}"
			),
		}
		if doctype in conditions:
			return conditions[doctype]

	if QUALITY_INSPECTOR_ROLE in roles:
		conditions = {
			"Inspection": f"`tabInspection`.assigned_to = {user_sql}",
			"Field Corrective Action": (
				f"`tabField Corrective Action`.verification_assigned_to = {user_sql}"
			),
			"Seed Harvest Quality Assessment": (
				f"`tabSeed Harvest Quality Assessment`.inspected_by = {user_sql}"
			),
			"Crop Cycle": (
				"exists (select 1 from `tabInspection` inspection "
				"where inspection.crop_cycle = `tabCrop Cycle`.name "
				f"and inspection.assigned_to = {user_sql})"
			),
			"Farm Plot": (
				"exists (select 1 from `tabInspection` inspection "
				"where inspection.plot = `tabFarm Plot`.name "
				f"and inspection.assigned_to = {user_sql})"
			),
			"Outgrower": (
				"exists (select 1 from `tabInspection` inspection "
				"where inspection.outgrower = `tabOutgrower`.name "
				f"and inspection.assigned_to = {user_sql})"
			),
			"Crop Production Lot": (
				"exists (select 1 from `tabInspection` inspection "
				"where inspection.crop_cycle = `tabCrop Production Lot`.crop_cycle "
				f"and inspection.assigned_to = {user_sql})"
			),
		}
		if doctype in conditions:
			return conditions[doctype]
	return "1 = 0"


def has_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	if _has_management_scope(user):
		return True
	condition = get_permission_query_conditions(user, doc.doctype)
	if not condition or condition == "1 = 0":
		return False
	return bool(
		frappe.db.sql(
			f"select name from `tab{doc.doctype}` where name = %s and ({condition}) limit 1",
			doc.name,
		)
	)


def outgrower_query(user=None):
	return get_permission_query_conditions(user, "Outgrower")


def farm_plot_query(user=None):
	return get_permission_query_conditions(user, "Farm Plot")


def crop_cycle_query(user=None):
	return get_permission_query_conditions(user, "Crop Cycle")


def stage_activity_query(user=None):
	return get_permission_query_conditions(user, "Stage Activity")


def agronomy_report_query(user=None):
	return get_permission_query_conditions(user, "Agronomy Report")


def inspection_query(user=None):
	return get_permission_query_conditions(user, "Inspection")


def corrective_action_query(user=None):
	return get_permission_query_conditions(user, "Field Corrective Action")


def production_lot_query(user=None):
	return get_permission_query_conditions(user, "Crop Production Lot")


def harvest_quality_query(user=None):
	return get_permission_query_conditions(user, "Seed Harvest Quality Assessment")
