# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint


OUTGROWER_SUPERVISOR_ROLE = "Outgrower Supervisor"
OUTGROWER_MANAGER_ROLE = "Outgrower Manager"
QUALITY_INSPECTOR_ROLE = "Quality Inspector"
FIELDOPS_FINANCE_APPROVER_ROLE = "FieldOps Finance Approver"
FIELDOPS_STORES_USER_ROLE = "FieldOps Stores User"
FIELDOPS_OPERATIONS_APPROVER_ROLE = "FieldOps Operations Approver"
QUALITY_MANAGER_ROLE = "Quality Manager"
FIELDOPS_ROLES = (
	OUTGROWER_SUPERVISOR_ROLE,
	OUTGROWER_MANAGER_ROLE,
	QUALITY_INSPECTOR_ROLE,
	FIELDOPS_FINANCE_APPROVER_ROLE,
	FIELDOPS_STORES_USER_ROLE,
	FIELDOPS_OPERATIONS_APPROVER_ROLE,
	QUALITY_MANAGER_ROLE,
)
MOBILE_FIELDOPS_ROLES = (OUTGROWER_SUPERVISOR_ROLE, QUALITY_INSPECTOR_ROLE)


def ensure_fieldops_roles():
	for role_name in FIELDOPS_ROLES:
		desk_access = 0 if role_name in MOBILE_FIELDOPS_ROLES else 1
		if frappe.db.exists("Role", role_name):
			frappe.db.set_value(
				"Role",
				role_name,
				{"disabled": 0, "desk_access": desk_access, "is_custom": 0},
				update_modified=False,
			)
			continue

		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"disabled": 0,
				"desk_access": desk_access,
				"is_custom": 0,
			}
		).insert(ignore_permissions=True)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def user_with_role_query(doctype, txt, searchfield, start, page_len, filters):
	role = (filters or {}).get("role")
	if role not in (*FIELDOPS_ROLES, QUALITY_MANAGER_ROLE):
		return []
	return frappe.db.sql(
		"""
		select distinct user.name, user.full_name
		from `tabUser` user
		inner join `tabHas Role` role
			on role.parent = user.name
			and role.parenttype = 'User'
			and role.role = %(role)s
		where user.enabled = 1
			and user.user_type = 'System User'
			and (
				user.name like %(txt)s
				or coalesce(user.full_name, '') like %(txt)s
			)
		order by user.full_name, user.name
		limit %(start)s, %(page_len)s
		""",
		{
			"role": role,
			"txt": f"%{txt}%",
			"start": cint(start),
			"page_len": cint(page_len),
		},
	)
