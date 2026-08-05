import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class StageActivity(Document):
	def validate(self):
		if self.status == "Completed":
			if self.mandatory and not (self.completion_notes or self.evidence):
				frappe.throw(
					_("Completion Notes or Evidence is required for a mandatory activity.")
				)
			self.completed_on = self.completed_on or now_datetime()
		elif self.has_value_changed("status"):
			self.completed_on = None

	def on_update(self):
		self.update_stage_progress()
		self.update_todo()

	def update_stage_progress(self):
		if not self.stage:
			return
		rows = frappe.get_all(
			"Stage Activity",
			filters={"stage": self.stage, "status": ["!=", "Cancelled"], "mandatory": 1},
			fields=["status"],
		)
		mandatory_count = len(rows)
		completed_count = len([row for row in rows if row.status == "Completed"])
		percentage = (
			round((completed_count / mandatory_count) * 100, 2)
			if mandatory_count
			else 0
		)
		report = frappe.db.get_value("Crop Cycle Stage", self.stage, "agronomy_report")
		report_submitted = (
			frappe.db.get_value("Agronomy Report", report, "docstatus") == 1 if report else False
		)
		stage_status = (
			"Completed"
			if mandatory_count == completed_count and report_submitted
			else "In Progress"
			if completed_count
			else "Pending"
		)
		if stage_status == "Completed":
			percentage = 100
		elif mandatory_count and mandatory_count == completed_count:
			percentage = 90
		frappe.db.set_value(
			"Crop Cycle Stage",
			self.stage,
			{
				"mandatory_activity_count": mandatory_count,
				"completed_activity_count": completed_count,
				"completion_percentage": percentage,
				"status": stage_status,
			},
			update_modified=False,
		)
		if stage_status == "Completed":
			from naseco_fieldopsbackend.inspection_scheduler import (
				update_crop_cycle_current_stage,
			)

			update_crop_cycle_current_stage(self.crop_cycle)

	def update_todo(self):
		if not self.assigned_to:
			return
		todo = frappe.db.get_value(
			"ToDo",
			{
				"reference_type": self.doctype,
				"reference_name": self.name,
				"allocated_to": self.assigned_to,
			},
		)
		if todo:
			frappe.db.set_value(
				"ToDo",
				todo,
				"status",
				"Closed" if self.status in ("Completed", "Cancelled") else "Open",
				update_modified=False,
			)
