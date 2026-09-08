import frappe

from naseco_fieldopsbackend.patches.configure_fieldops_operating_model import ROLE_PERMISSIONS
from naseco_fieldopsbackend.roles import OUTGROWER_MANAGER_ROLE


def execute():
	"""Enable standard list/form deletion without replacing other custom permissions."""
	for doctype, flags in ROLE_PERMISSIONS[OUTGROWER_MANAGER_ROLE].items():
		if "d" not in flags or not frappe.db.exists("DocType", doctype):
			continue
		for name in frappe.get_all(
			"Custom DocPerm",
			filters={"parent": doctype, "role": OUTGROWER_MANAGER_ROLE, "permlevel": 0},
			pluck="name",
		):
			frappe.db.set_value("Custom DocPerm", name, "delete", 1)
		frappe.clear_cache(doctype=doctype)
