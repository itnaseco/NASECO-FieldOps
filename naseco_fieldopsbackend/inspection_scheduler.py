# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

from naseco_fieldopsbackend.crop_cycle_lifecycle import LIFECYCLE_STAGES, get_stage


@frappe.whitelist()
def generate_crop_cycle_schedules_for_doc(crop_cycle):
	"""Generate all post-planting schedules for a planted crop cycle."""
	doc = frappe.get_doc("Crop Cycle", crop_cycle)
	if not doc.planting_date or not doc.production_category:
		frappe.throw(_("Planting Date and Production Category are required before generating schedules."))
	sync_crop_cycle_lifecycle(doc)
	frappe.db.commit()
	return {
		"lifecycle_initialized": doc.lifecycle_initialized,
		"inspection_schedule_generated": doc.inspection_schedule_generated,
		"agronomy_schedule_generated": doc.agronomy_schedule_generated,
		"agronomy_report_schedule_generated": doc.agronomy_report_schedule_generated,
	}


def generate_crop_cycle_schedules(crop_cycle):
	"""Backward-compatible entry point used by seed scripts and integrations."""
	return sync_crop_cycle_lifecycle(crop_cycle)


def sync_crop_cycle_lifecycle(crop_cycle):
	"""Idempotently synchronize lifecycle stages and all operational schedules."""
	if not crop_cycle.name:
		return

	stages = ensure_crop_cycle_stages(crop_cycle)
	create_agronomy_reports(crop_cycle, stages)
	create_agronomy_activities(crop_cycle, stages)
	if crop_cycle.planting_date and crop_cycle.production_category:
		create_inspections(crop_cycle)

	flags = {
		"lifecycle_initialized": 1,
		"inspection_schedule_generated": int(
			bool(crop_cycle.planting_date and crop_cycle.production_category)
		),
		"agronomy_schedule_generated": int(bool(crop_cycle.planting_date)),
		"agronomy_report_schedule_generated": int(bool(crop_cycle.planting_date)),
	}
	crop_cycle.db_set(flags, update_modified=False)
	for fieldname, value in flags.items():
		crop_cycle.set(fieldname, value)
	update_crop_cycle_current_stage(crop_cycle.name)
	return flags


def get_recipe_stages(crop_cycle):
	if not crop_cycle.recipe:
		return list(LIFECYCLE_STAGES)
	rows = frappe.get_all(
		"Recipe Stage",
		filters={
			"parent": crop_cycle.recipe,
			"parenttype": "Crop Recipe",
			"parentfield": "stages",
		},
		fields=[
			"stage_code",
			"stage_name",
			"order_index",
			"start_day_offset",
			"end_day_offset",
		],
		order_by="order_index asc, idx asc",
	)
	resolved = []
	for row in rows:
		stage = get_stage(row.stage_code or row.stage_name)
		if not stage:
			continue
		resolved.append(
			frappe._dict(
				{
					"code": stage.code,
					"name": stage.name,
					"order": row.order_index or stage.order,
					"start_day": (
						row.start_day_offset
						if row.start_day_offset is not None
						else stage.start_day
					),
					"end_day": (
						row.end_day_offset
						if row.end_day_offset is not None
						else stage.end_day
					),
				}
			)
		)
	return resolved if len(resolved) == len(LIFECYCLE_STAGES) else list(LIFECYCLE_STAGES)


def ensure_crop_cycle_stages(crop_cycle):
	anchor = crop_cycle.planting_date
	planned_anchor = crop_cycle.start_date
	stage_docs = {}
	for definition in get_recipe_stages(crop_cycle):
		stage_anchor = anchor
		if definition.code == "FIELD_VERIFICATION" and not stage_anchor:
			stage_anchor = planned_anchor
		start_date = add_days(stage_anchor, definition.start_day) if stage_anchor else None
		end_date = add_days(stage_anchor, definition.end_day) if stage_anchor else None

		existing = frappe.db.get_value(
			"Crop Cycle Stage",
			{"crop_cycle": crop_cycle.name, "stage_code": definition.code},
		)
		if not existing:
			existing = frappe.db.get_value(
				"Crop Cycle Stage",
				{"crop_cycle": crop_cycle.name, "stage_name": definition.name},
			)
		if existing:
			doc = frappe.get_doc("Crop Cycle Stage", existing)
			if doc.status in ("Pending", "In Progress"):
				doc.db_set(
					{
						"stage_code": definition.code,
						"stage_name": definition.name,
						"order_index": definition.order,
						"start_date": start_date,
						"end_date": end_date,
						"duration_days": definition.end_day - definition.start_day + 1,
						"crop": crop_cycle.crop,
					},
					update_modified=False,
				)
		else:
			doc = frappe.get_doc(
				{
					"doctype": "Crop Cycle Stage",
					"stage_id": f"{crop_cycle.name}-{definition.code}",
					"crop_cycle": crop_cycle.name,
					"stage_code": definition.code,
					"stage_name": definition.name,
					"order_index": definition.order,
					"start_date": start_date,
					"end_date": end_date,
					"duration_days": definition.end_day - definition.start_day + 1,
					"status": "Pending",
					"crop": crop_cycle.crop,
				}
			).insert(ignore_permissions=True)
		stage_docs[definition.name] = doc
	return stage_docs


def create_agronomy_reports(crop_cycle, stages):
	templates = frappe.get_all(
		"Agronomy Report Template",
		filters={"active": 1},
		fields=[
			"name",
			"report_number",
			"stage_name",
			"window_start_day",
			"window_end_day",
		],
		order_by="report_number asc",
	)
	for template in templates:
		if template.report_number > 1 and not crop_cycle.planting_date:
			continue
		stage = stages.get(template.stage_name)
		if not stage:
			continue
		anchor = crop_cycle.planting_date or crop_cycle.start_date
		if not anchor:
			continue
		window_start = add_days(anchor, template.window_start_day)
		window_end = add_days(anchor, template.window_end_day)
		existing = frappe.db.get_value(
			"Agronomy Report",
			{
				"crop_cycle": crop_cycle.name,
				"report_template": template.name,
				"docstatus": ["<", 2],
			},
		)
		if existing:
			report = frappe.get_doc("Agronomy Report", existing)
			if report.docstatus == 0:
				report.db_set(
					{
						"stage": stage.name,
						"stage_name": template.stage_name,
						"window_start_date": window_start,
						"window_end_date": window_end,
					},
					update_modified=False,
				)
		else:
			report = frappe.get_doc(
				{
					"doctype": "Agronomy Report",
					"report_template": template.name,
					"report_number": template.report_number,
					"crop_cycle": crop_cycle.name,
					"stage": stage.name,
					"stage_name": template.stage_name,
					"window_start_date": window_start,
					"window_end_date": window_end,
					"report_date": window_start,
					"status": "Scheduled",
				}
			)
			report.flags.ignore_mandatory = True
			report.insert(ignore_permissions=True)
			create_todo(
				report.assigned_supervisor,
				"Agronomy Report",
				report.name,
				_("Complete Report {0}: {1}").format(
					template.report_number, template.stage_name
				),
				window_end,
				"High",
			)
		stage.db_set("agronomy_report", report.name, update_modified=False)


def create_inspections(crop_cycle):
	plot = frappe.get_doc("Farm Plot", crop_cycle.plot) if crop_cycle.plot else None
	outgrower = frappe.get_doc("Outgrower", plot.outgrower) if plot and plot.outgrower else None
	templates = frappe.get_all(
		"Inspection Template",
		filters={"active": 1},
		fields=["name", "inspection_type", "due_days_from_planting", "default_assigned_to"],
		order_by="due_days_from_planting asc",
	)
	scheduled_dates = []
	for template in templates:
		scheduled_date = add_days(crop_cycle.planting_date, template.due_days_from_planting or 0)
		assigned_inspector = get_quality_inspector(
			crop_cycle, template.default_assigned_to, outgrower
		)
		existing = frappe.db.get_value(
			"Inspection",
			{
				"crop_cycle": crop_cycle.name,
				"inspection_template": template.name,
				"status": ["!=", "Cancelled"],
			},
		)
		if existing:
			inspection = frappe.get_doc("Inspection", existing)
			if inspection.status == "Scheduled":
				inspection.db_set("scheduled_date", scheduled_date, update_modified=False)
			scheduled_dates.append(inspection.scheduled_date or scheduled_date)
			continue
		inspection = frappe.get_doc(
			{
				"doctype": "Inspection",
				"inspection_template": template.name,
				"inspection_type": template.inspection_type,
				"crop_cycle": crop_cycle.name,
				"production_contract": crop_cycle.production_contract,
				"plot": crop_cycle.plot,
				"outgrower": outgrower.name if outgrower else None,
				"crop": crop_cycle.crop,
				"season": crop_cycle.season,
				"production_category": crop_cycle.production_category,
				"scheduled_date": scheduled_date,
				"assigned_to": assigned_inspector,
				"status": "Scheduled",
			}
		).insert(ignore_permissions=True)
		scheduled_dates.append(scheduled_date)
		create_todo(
			assigned_inspector,
			"Inspection",
			inspection.name,
			_("{0} inspection for {1}").format(template.inspection_type, crop_cycle.name),
			scheduled_date,
			"High",
		)
	if scheduled_dates:
		future_dates = [date for date in scheduled_dates if getdate(date) >= getdate(nowdate())]
		crop_cycle.db_set(
			"next_inspection_date",
			min(future_dates or scheduled_dates),
			update_modified=False,
		)


def get_quality_inspector(crop_cycle, template_default=None, outgrower=None):
	if template_default and "Quality Inspector" in frappe.get_roles(template_default):
		return template_default

	plan = frappe.db.get_value(
		"Season Production Plan",
		{
			"season": crop_cycle.season,
			"company": crop_cycle.company,
			"status": ["in", ["Approved", "Active"]],
			"docstatus": 1,
		},
		"name",
	)
	if not plan:
		return None
	region = outgrower.region if outgrower else None
	candidates = frappe.db.sql(
		"""
		select allocation.user
		from `tabSeason Resource Allocation` allocation
		where allocation.parent = %(plan)s
			and allocation.parenttype = 'Season Production Plan'
			and allocation.resource_role = 'Quality Inspector'
			and allocation.active = 1
			and (ifnull(allocation.region, '') = '' or allocation.region = %(region)s)
		order by (
			select count(*) from `tabInspection` inspection
			where inspection.assigned_to = allocation.user
				and inspection.season = %(season)s
				and inspection.status not in ('Verified', 'Cancelled')
		), allocation.idx
		limit 1
		""",
		{"plan": plan, "region": region or "", "season": crop_cycle.season},
	)
	return candidates[0][0] if candidates else None


def create_agronomy_activities(crop_cycle, stages):
	plot = frappe.get_doc("Farm Plot", crop_cycle.plot) if crop_cycle.plot else None
	outgrower = frappe.get_doc("Outgrower", plot.outgrower) if plot and plot.outgrower else None
	assigned_to = outgrower.assigned_supervisor if outgrower else None
	templates = frappe.get_all(
		"Agronomy Activity Template",
		filters={"active": 1},
		fields=[
			"name",
			"activity_name",
			"crop_recipe",
			"stage_name",
			"day_offset_from_planting",
			"day_offset_end",
			"description",
			"priority",
			"mandatory",
			"evidence_required",
		],
		order_by="day_offset_from_planting asc",
	)
	for template in templates:
		if template.crop_recipe and template.crop_recipe != crop_cycle.recipe:
			continue
		if not crop_cycle.planting_date and template.day_offset_from_planting >= 0:
			continue
		anchor = crop_cycle.planting_date or crop_cycle.start_date
		if not anchor:
			continue
		activity_date = add_days(anchor, template.day_offset_from_planting or 0)
		due_date = add_days(anchor, template.day_offset_end or template.day_offset_from_planting or 0)
		activity_id = f"{crop_cycle.name}-{template.name}"
		existing = frappe.db.get_value("Stage Activity", {"activity_id": activity_id})
		stage = stages.get(template.stage_name)
		if existing:
			activity = frappe.get_doc("Stage Activity", existing)
			if not activity.activity_template:
				activity.db_set(
					"activity_template",
					template.name,
					update_modified=False,
				)
			if activity.status == "Scheduled":
				activity.db_set(
					{
						"stage": stage.name if stage else None,
						"activity_date": activity_date,
						"due_date": due_date,
						"assigned_to": assigned_to,
					},
					update_modified=False,
				)
			continue
		activity = frappe.get_doc(
			{
				"doctype": "Stage Activity",
				"activity_id": activity_id,
				"activity_template": template.name,
				"crop_cycle": crop_cycle.name,
				"stage": stage.name if stage else None,
				"title": template.activity_name,
				"description": template.description,
				"activity_date": activity_date,
				"due_date": due_date,
				"assigned_to": assigned_to,
				"priority": template.priority,
				"mandatory": template.mandatory,
				"status": "Scheduled",
			}
		).insert(ignore_permissions=True)
		create_todo(
			assigned_to,
			"Stage Activity",
			activity.name,
			_("Agronomy activity: {0}").format(template.activity_name),
			due_date,
			template.priority or "Medium",
		)


def update_crop_cycle_current_stage(crop_cycle):
	stages = frappe.get_all(
		"Crop Cycle Stage",
		filters={"crop_cycle": crop_cycle},
		fields=["name", "order_index", "start_date", "end_date", "status"],
		order_by="order_index asc",
	)
	if not stages:
		return
	today = getdate(nowdate())
	current = next(
		(
			row
			for row in stages
			if row.status != "Completed"
			and row.start_date
			and row.end_date
			and getdate(row.start_date) <= today <= getdate(row.end_date)
		),
		None,
	)
	if not current:
		current = next((row for row in stages if row.status != "Completed"), stages[-1])
	frappe.db.set_value(
		"Crop Cycle",
		crop_cycle,
		"current_stage",
		current.name,
		update_modified=False,
	)


def create_todo(allocated_to, reference_type, reference_name, description, date=None, priority="Medium"):
	if not allocated_to:
		return
	if frappe.db.exists(
		"ToDo",
		{
			"reference_type": reference_type,
			"reference_name": reference_name,
			"allocated_to": allocated_to,
		},
	):
		return
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": allocated_to,
			"reference_type": reference_type,
			"reference_name": reference_name,
			"description": description,
			"date": date,
			"status": "Open",
			"priority": priority,
		}
	).insert(ignore_permissions=True)
