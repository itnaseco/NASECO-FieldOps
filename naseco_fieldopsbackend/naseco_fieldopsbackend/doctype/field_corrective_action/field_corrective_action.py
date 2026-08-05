# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class FieldCorrectiveAction(Document):
	def before_validate(self):
		if self.inspection:
			self.source_type = "Inspection"
			self.source_name = self.inspection
			self.source_parameter = self.source_parameter or self.parameter
		elif self.agronomy_report:
			self.source_type = "Agronomy Report"
			self.source_name = self.agronomy_report
		if self.source_type == "Inspection":
			self.inspection = self.source_name
		elif self.source_type == "Agronomy Report":
			self.agronomy_report = self.source_name

	def validate(self):
		if not self.source_name:
			frappe.throw("A source Inspection or Agronomy Report is required.")
		if self.verification_assigned_to and "Quality Inspector" not in frappe.get_roles(
			self.verification_assigned_to
		):
			frappe.throw(
				_("{0} must have the Quality Inspector role.").format(
					frappe.bold(self.verification_assigned_to)
				)
			)
		previous_status = (
			frappe.db.get_value(self.doctype, self.name, "status") if not self.is_new() else None
		)
		roles = set(frappe.get_roles(frappe.session.user))
		is_administrator = frappe.session.user == "Administrator"
		if self.status == "Responded" and previous_status != "Responded":
			if not self.resolution_notes:
				frappe.throw(_("Resolution Notes are required before submitting a response."))
			self.response_on = now_datetime()
		if self.status == "Verified" and previous_status != "Verified":
			if not is_administrator and not {
				"Quality Inspector",
				"Quality Manager",
			}.intersection(roles):
				frappe.throw(
					_("Only a Quality Inspector or Quality Manager may verify corrective work."),
					frappe.PermissionError,
				)
			if not self.verification_notes:
				frappe.throw(_("Verification Notes are required before verification."))
			self.verified_by = frappe.session.user
			self.verified_on = now_datetime()
		if self.status == "Closed" and not self.resolution_notes:
			frappe.throw("Resolution Notes are required to close a corrective action.")
		if (
			self.status == "Closed"
			and previous_status != "Closed"
			and not is_administrator
			and "Quality Manager" not in roles
		):
			frappe.throw(
				_("Only a Quality Manager may close a verified corrective action."),
				frappe.PermissionError,
			)
		if self.status == "Closed" and not self.verified_on:
			frappe.throw(_("A corrective action must be verified before it can be closed."))
		if self.status == "Closed" and not self.closed_on:
			self.closed_on = now_datetime()

	def on_update(self):
		self.sync_todo_status()
		self.create_todo()

	def create_todo(self):
		allocated_to = (
			self.verification_assigned_to if self.status == "Responded" else self.assigned_to
		)
		if not allocated_to or self.status in ("Verified", "Closed", "Cancelled"):
			return
		if frappe.db.exists(
			"ToDo",
			{
				"reference_type": self.doctype,
				"reference_name": self.name,
				"allocated_to": allocated_to,
				"status": "Open",
			},
		):
			return
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": allocated_to,
				"reference_type": self.doctype,
				"reference_name": self.name,
				"description": (
					f"Verify corrective action {self.name}"
					if self.status == "Responded"
					else self.description or f"Resolve corrective action {self.name}"
				),
				"date": self.due_date,
				"status": "Open",
				"priority": "High",
			}
		).insert(ignore_permissions=True)

	def sync_todo_status(self):
		todos = frappe.get_all(
			"ToDo",
			filters={"reference_type": self.doctype, "reference_name": self.name},
			pluck="name",
		)
		for todo in todos:
			frappe.db.set_value(
				"ToDo",
				todo,
				"status",
				"Closed" if self.status in ("Responded", "Verified", "Closed", "Cancelled") else "Open",
				update_modified=False,
			)
