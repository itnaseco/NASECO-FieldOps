# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe

from naseco_fieldopsbackend.roles import (
	FIELDOPS_FINANCE_APPROVER_ROLE,
	FIELDOPS_OPERATIONS_APPROVER_ROLE,
	FIELDOPS_STORES_USER_ROLE,
	OUTGROWER_MANAGER_ROLE,
	OUTGROWER_SUPERVISOR_ROLE,
	QUALITY_INSPECTOR_ROLE,
	QUALITY_MANAGER_ROLE,
	ensure_fieldops_roles,
)


ROLE_PROFILES = {
	"FieldOps Outgrower Manager": [OUTGROWER_MANAGER_ROLE],
	"FieldOps Quality Manager": [QUALITY_MANAGER_ROLE],
	"FieldOps Quality Inspector": [QUALITY_INSPECTOR_ROLE],
	"FieldOps Mobile Supervisor": [OUTGROWER_SUPERVISOR_ROLE],
	"FieldOps Finance": [FIELDOPS_FINANCE_APPROVER_ROLE, "Accounts User", "Purchase User"],
	"FieldOps Stores": [FIELDOPS_STORES_USER_ROLE, "Stock User", "Purchase User"],
	"FieldOps Operations Approver": [FIELDOPS_OPERATIONS_APPROVER_ROLE],
}

READ_ONLY_MASTERS = (
	"Season",
	"Crop",
	"Crop Variety",
	"Seed Category",
	"Seed Class",
	"Region",
	"UOM",
	"Crop Recipe",
	"Crop Cycle Stage",
	"Inspection Attribute",
	"Inspection Parameter",
	"Inspection Template",
	"Inspection Standard",
	"Agronomy Activity Template",
	"Agronomy Report Template",
	"Production Contract Template",
	"Outgrower Pricing Policy",
)

ROLE_PERMISSIONS = {
	OUTGROWER_SUPERVISOR_ROLE: {
		"Outgrower": "r",
		"Farm Plot": "r",
		"Crop Cycle": "r",
		"Outgrower Production Contract": "r",
		"Stage Activity": "rwc",
		"Agronomy Report": "rwc",
		"Field Corrective Action": "rw",
		"Stage Input Request": "rwc",
		"Stage Input Dispatch": "r",
	},
	QUALITY_INSPECTOR_ROLE: {
		"Outgrower": "r",
		"Farm Plot": "r",
		"Crop Cycle": "r",
		"Outgrower Production Contract": "r",
		"Crop Production Lot": "r",
		"Inspection": "rwc",
		"Field Corrective Action": "rwc",
		"Seed Harvest Quality Assessment": "rwc",
	},
	QUALITY_MANAGER_ROLE: {
		"Season Production Plan": "rw",
		"Inspection": "rwc",
		"Field Corrective Action": "rwc",
		"Seed Harvest Quality Assessment": "rwcsx",
		"Crop Production Lot": "r",
	},
	OUTGROWER_MANAGER_ROLE: {
		"Season": "rwc",
		"Crop": "rwc",
		"Crop Variety": "rwc",
		"Crop Recipe": "rwcdsx",
		"Seed Category": "rwc",
		"Seed Class": "rwc",
		"Region": "rwc",
		"Location": "rwc",
		"Season Production Plan": "rwcsx",
		"Outgrower": "rwc",
		"Farm Plot": "rwc",
		"Crop Cycle": "rwc",
		"Outgrower Production Contract": "rwcs",
		"Stage Activity": "rwc",
		"Agronomy Report": "rwc",
		"Inspection": "r",
		"Field Corrective Action": "r",
		"Stage Input Request": "rwc",
		"Stage Input Dispatch": "r",
		"Crop Cycle Advance Request": "rwc",
		"Crop Cycle Settlement": "rwc",
		"Crop Production Lot": "rwc",
		"Seed Harvest Quality Assessment": "r",
	},
	"Administrator": {
		"Season": "rwcd",
		"Crop": "rwcd",
		"Crop Variety": "rwcd",
		"Seed Category": "rwcd",
		"Seed Class": "rwcd",
		"Region": "rwcd",
		"Location": "rwcd",
	},
	FIELDOPS_FINANCE_APPROVER_ROLE: {
		"Season Production Plan": "rw",
		"Outgrower Production Contract": "r",
		"Crop Cycle": "r",
		"Crop Cycle Advance Request": "rwcs",
		"Crop Cycle Settlement": "rwcs",
	},
	FIELDOPS_STORES_USER_ROLE: {
		"Season Production Plan": "rw",
		"Outgrower Production Contract": "r",
		"Crop Cycle": "r",
		"Stage Input Request": "rw",
		"Stage Input Dispatch": "rwc",
		"Crop Production Lot": "rw",
	},
	FIELDOPS_OPERATIONS_APPROVER_ROLE: {"Season Production Plan": "rwsx"},
}


def execute():
	ensure_fieldops_roles()
	ensure_role_profiles()
	ensure_custom_permissions()
	ensure_production_plan_workflow()
	frappe.clear_cache()


def ensure_role_profiles():
	for profile_name, roles in ROLE_PROFILES.items():
		doc = (
			frappe.get_doc("Role Profile", profile_name)
			if frappe.db.exists("Role Profile", profile_name)
			else frappe.new_doc("Role Profile")
		)
		doc.role_profile = profile_name
		doc.set("roles", [])
		for role in roles:
			if frappe.db.exists("Role", role):
				doc.append("roles", {"role": role})
		doc.save(ignore_permissions=True)


def ensure_custom_permissions():
	for role in (
		OUTGROWER_SUPERVISOR_ROLE,
		QUALITY_INSPECTOR_ROLE,
		QUALITY_MANAGER_ROLE,
		OUTGROWER_MANAGER_ROLE,
	):
		for doctype in READ_ONLY_MASTERS:
			ROLE_PERMISSIONS.setdefault(role, {}).setdefault(doctype, "r")

	for role, doctypes in ROLE_PERMISSIONS.items():
		for doctype, flags in doctypes.items():
			if not frappe.db.exists("DocType", doctype):
				continue
			filters = {"parent": doctype, "role": role, "permlevel": 0}
			name = frappe.db.exists("Custom DocPerm", filters)
			doc = frappe.get_doc("Custom DocPerm", name) if name else frappe.new_doc("Custom DocPerm")
			doc.update(
				{
					"parent": doctype,
					"role": role,
					"permlevel": 0,
					"read": int("r" in flags),
					"write": int("w" in flags),
					"create": int("c" in flags),
					"delete": int("d" in flags),
					"submit": int("s" in flags),
					"cancel": int("x" in flags),
					"report": int("r" in flags),
					"print": int("r" in flags),
					"email": int("r" in flags),
				}
			)
			doc.save(ignore_permissions=True)


def ensure_production_plan_workflow():
	states = (
		"Draft",
		"Under Review",
		"Awaiting Approval",
		"Approved",
		"Active",
		"Closing",
		"Closed",
		"Cancelled",
	)
	actions = (
		"Submit for Department Review",
		"Complete Quality Review",
		"Approve Production Plan",
		"Activate Season Plan",
		"Start Season Closure",
		"Close Season Plan",
		"Cancel Season Plan",
	)
	for state in states:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state}
			).insert(ignore_permissions=True)
	for action in actions:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": action}
			).insert(ignore_permissions=True)

	data = {
		"workflow_name": "Season Production Plan Approval",
		"document_type": "Season Production Plan",
		"is_active": 1,
		"override_status": 0,
		"send_email_alert": 1,
		"workflow_state_field": "status",
		"states": [
			{"state": "Draft", "doc_status": "0", "allow_edit": OUTGROWER_MANAGER_ROLE},
			{"state": "Under Review", "doc_status": "0", "allow_edit": OUTGROWER_MANAGER_ROLE},
			{
				"state": "Awaiting Approval",
				"doc_status": "0",
				"allow_edit": FIELDOPS_OPERATIONS_APPROVER_ROLE,
			},
			{"state": "Approved", "doc_status": "1", "allow_edit": OUTGROWER_MANAGER_ROLE},
			{"state": "Active", "doc_status": "1", "allow_edit": OUTGROWER_MANAGER_ROLE},
			{"state": "Closing", "doc_status": "1", "allow_edit": OUTGROWER_MANAGER_ROLE},
			{
				"state": "Closed",
				"doc_status": "1",
				"allow_edit": FIELDOPS_OPERATIONS_APPROVER_ROLE,
			},
			{
				"state": "Cancelled",
				"doc_status": "2",
				"allow_edit": FIELDOPS_OPERATIONS_APPROVER_ROLE,
			},
		],
		"transitions": [
			{
				"state": "Draft",
				"action": "Submit for Department Review",
				"next_state": "Under Review",
				"allowed": OUTGROWER_MANAGER_ROLE,
			},
			{
				"state": "Under Review",
				"action": "Complete Quality Review",
				"next_state": "Awaiting Approval",
				"allowed": QUALITY_MANAGER_ROLE,
			},
			{
				"state": "Awaiting Approval",
				"action": "Approve Production Plan",
				"next_state": "Approved",
				"allowed": FIELDOPS_OPERATIONS_APPROVER_ROLE,
				"allow_self_approval": 0,
			},
			{
				"state": "Approved",
				"action": "Activate Season Plan",
				"next_state": "Active",
				"allowed": OUTGROWER_MANAGER_ROLE,
			},
			{
				"state": "Active",
				"action": "Start Season Closure",
				"next_state": "Closing",
				"allowed": OUTGROWER_MANAGER_ROLE,
			},
			{
				"state": "Closing",
				"action": "Close Season Plan",
				"next_state": "Closed",
				"allowed": FIELDOPS_OPERATIONS_APPROVER_ROLE,
			},
			*[
				{
					"state": state,
					"action": "Cancel Season Plan",
					"next_state": "Cancelled",
					"allowed": FIELDOPS_OPERATIONS_APPROVER_ROLE,
				}
				for state in ("Approved", "Active", "Closing")
			],
		],
	}
	name = frappe.db.exists("Workflow", data["workflow_name"])
	workflow = frappe.get_doc("Workflow", name) if name else frappe.new_doc("Workflow")
	workflow.update(data)
	workflow.save(ignore_permissions=True)
