import frappe
from frappe.permissions import setup_custom_perms

from naseco_fieldopsbackend.roles import OUTGROWER_MANAGER_ROLE


def execute():
	"""Grant supplier cleanup access while preserving existing ERPNext permissions."""
	if not frappe.db.exists("DocType", "Supplier"):
		return
	setup_custom_perms("Supplier")
	filters = {
		"parent": "Supplier",
		"role": OUTGROWER_MANAGER_ROLE,
		"permlevel": 0,
		"if_owner": 0,
	}
	name = frappe.db.exists("Custom DocPerm", filters)
	permission = frappe.get_doc("Custom DocPerm", name) if name else frappe.new_doc("Custom DocPerm")
	permission.update({**filters, "parenttype": "DocType", "parentfield": "permissions", "read": 1, "delete": 1})
	permission.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Supplier")
