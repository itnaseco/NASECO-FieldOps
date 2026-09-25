# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, nowdate

from naseco_fieldopsbackend.crop_cycle_lifecycle import LIFECYCLE_STAGES, get_stage


@frappe.whitelist()
def generate_crop_cycle_schedules_for_doc(crop_cycle):
	"""Generate all post-planting schedules for a planted crop cycle."""
	doc = frappe.get_doc("Crop Cycle", crop_cycle)
	if not doc.planting_date_confirmed:
		frappe.throw(_("Confirm the Planting Date before generating schedules."))
	sync_crop_cycle_lifecycle(doc, require_inspection_templates=True)
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


def sync_crop_cycle_lifecycle(crop_cycle, require_inspection_templates=False):
	"""Idempotently synchronize lifecycle stages and all operational schedules."""
	if not crop_cycle.name or not crop_cycle.get("planting_date_confirmed"):
		return

	stages = ensure_crop_cycle_stages(crop_cycle)
	create_agronomy_reports(crop_cycle, stages)
	create_agronomy_activities(crop_cycle, stages)
	inspection_count = 0
	if crop_cycle.planting_date and crop_cycle.production_category:
		inspection_count = create_inspections(crop_cycle)
		if require_inspection_templates and not inspection_count:
			frappe.throw(
				_(
					"No active Published Inspection Template is available. "
					"Publish at least one template before confirming the Planting Date."
				),
				title=_("Quality Inspection Schedule Not Generated"),
			)

	flags = {
		"lifecycle_initialized": 1,
		"inspection_schedule_generated": int(bool(inspection_count)),
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


def inspection_lifecycle_stage_name(inspection_type):
	"""Map operational inspection names to the canonical crop-cycle stage."""
	normalized = (inspection_type or "").strip().casefold().replace("-", " ")
	if normalized in {"1st flowering", "2nd flowering", "3rd flowering"}:
		return "Flowering"
	if normalized == "pre flowering":
		return "Pre-flowering"
	if normalized == "pre harvest":
		return "Pre-harvest"
	return None


def create_inspections(crop_cycle):
	plot = frappe.get_doc("Farm Plot", crop_cycle.plot) if crop_cycle.plot else None
	outgrower = frappe.get_doc("Outgrower", plot.outgrower) if plot and plot.outgrower else None
	# Fetch active templates first and resolve lifecycle state in Python. Older
	# installations can contain active templates with a blank lifecycle_status;
	# those are the pre-versioning equivalent of Published and must remain
	# schedulable after the scalable quality-configuration migration.
	templates = frappe.get_all(
		"Inspection Template",
		filters={"active": 1},
		fields=["name", "inspection_type", "crop_stage", "due_days_from_planting", "default_assigned_to", "configuration_version", "lifecycle_status"],
		order_by="due_days_from_planting asc",
	)
	templates = resolve_inspection_templates(templates)
	templates = select_applicable_inspection_templates(
		crop_cycle, templates, outgrower=outgrower
	)
	scheduled_dates = []
	for template in templates:
		scheduled_date = add_days(crop_cycle.planting_date, template.due_days_from_planting or 0)
		assigned_inspector = get_quality_inspector(
			crop_cycle, template.default_assigned_to, outgrower
		)
		stage_name = inspection_lifecycle_stage_name(template.inspection_type)
		stage = frappe.db.get_value(
			"Crop Cycle Stage",
			{"crop_cycle": crop_cycle.name, "stage_name": stage_name},
		) if stage_name else None
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
			if stage and not inspection.stage:
				inspection.db_set("stage", stage, update_modified=False)
			if not inspection.configuration_snapshot:
				inspection.db_set(
					{
						"template_version": template.configuration_version or 1,
						"configuration_snapshot": inspection_configuration_snapshot(template.name),
					},
					update_modified=False,
				)
			scheduled_dates.append(inspection.scheduled_date or scheduled_date)
			continue
		inspection = frappe.get_doc(
			{
				"doctype": "Inspection",
				"inspection_template": template.name,
				"template_version": template.configuration_version or 1,
				"configuration_snapshot": inspection_configuration_snapshot(template.name),
				"inspection_type": template.inspection_type,
				"crop_cycle": crop_cycle.name,
				"stage": stage,
				"production_contract": crop_cycle.production_contract,
				"plot": crop_cycle.plot,
				"outgrower": outgrower.name if outgrower else None,
				"crop": crop_cycle.crop,
				"season": crop_cycle.season,
				"production_category": crop_cycle.production_category,
				"seed_class": crop_cycle.seed_class,
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
	return len(scheduled_dates)


def resolve_inspection_templates(templates):
	"""Return versions that may generate new inspection schedules.

	Blank lifecycle state is accepted only for active legacy rows fetched by
	``create_inspections``. Draft and Retired versions never generate work.
	"""
	return [
		template
		for template in templates
		if not template.lifecycle_status or template.lifecycle_status == "Published"
	]


def select_applicable_inspection_templates(crop_cycle, templates, outgrower=None):
	"""Choose one deterministic template version per inspection type.

	Templates without rules are global fallbacks. A matching plot/outgrower rule
	wins over region/crop/global rules. Equal-scoring templates are rejected
	because silently scheduling both would create ambiguous field work.
	"""
	selected = {}
	for template in templates:
		score = _template_applicability_score(template.name, crop_cycle, outgrower)
		if score is None:
			continue
		key = (template.inspection_type or template.name).strip().casefold()
		current = selected.get(key)
		if current and current[0] == score and current[1].name != template.name:
			frappe.throw(
				_("Inspection templates {0} and {1} have equally specific applicability rules for Crop Cycle {2}.").format(
					frappe.bold(current[1].name), frappe.bold(template.name), frappe.bold(crop_cycle.name)
				),
				title=_("Ambiguous Quality Inspection Configuration"),
			)
		if not current or score > current[0]:
			selected[key] = (score, template)
	return [item[1] for item in selected.values()]


def _template_applicability_score(template, crop_cycle, outgrower=None):
	if not frappe.db.exists("DocType", "Inspection Template Applicability"):
		return 0
	rules = frappe.get_all(
		"Inspection Template Applicability",
		filters={"parent": template, "parenttype": "Inspection Template", "active": 1},
		fields=["*"],
	)
	if not rules:
		return 0
	context = {
		"crop": crop_cycle.get("crop"),
		"variety": crop_cycle.get("variety"),
		"production_category": crop_cycle.get("production_category"),
		"seed_class": crop_cycle.get("seed_class"),
		"region": outgrower.get("region") if outgrower else None,
		"season": crop_cycle.get("season"),
		"outgrower": outgrower.name if outgrower else None,
		"plot": crop_cycle.get("plot"),
	}
	weights = {
		"plot": 1000,
		"outgrower": 900,
		"region": 500,
		"variety": 300,
		"crop": 200,
		"seed_class": 120,
		"production_category": 100,
		"season": 50,
	}
	anchor = getdate(crop_cycle.planting_date) if crop_cycle.get("planting_date") else getdate(nowdate())
	matches = []
	for rule in rules:
		if rule.effective_from and anchor < getdate(rule.effective_from):
			continue
		if rule.effective_to and anchor > getdate(rule.effective_to):
			continue
		if any(rule.get(field) and rule.get(field) != context.get(field) for field in weights):
			continue
		specificity = sum(weight for field, weight in weights.items() if rule.get(field))
		matches.append(cint(rule.priority) * 10000 + specificity)
	return max(matches) if matches else None


def get_template_standard_rows(template):
	"""Return template-owned rows, falling back to legacy Standard records."""
	if frappe.db.exists("DocType", "Inspection Template Parameter"):
		rows = frappe.get_all(
			"Inspection Template Parameter",
			filters={"parent": template, "parenttype": "Inspection Template", "active": 1},
			fields=["*"],
			order_by="display_order asc, idx asc",
		)
		if rows:
			for row in rows:
				row.inspection_template = template
			return rows
	return frappe.get_all(
		"Inspection Standard",
		filters={"inspection_template": template},
		fields=["*"],
		order_by="display_order asc, creation asc, parameter asc",
	)


def inspection_configuration_snapshot(template):
	standards = get_template_standard_rows(template)
	parameter_names = sorted({row.parameter for row in standards if row.parameter})
	parameters = (
		frappe.get_all(
			"Inspection Parameter",
			filters={"name": ["in", parameter_names]},
			fields=["*"],
		)
		if parameter_names else []
	)
	return json.dumps(
		{
			"template": template,
			"version": frappe.db.get_value("Inspection Template", template, "configuration_version") or 1,
			"captured_at": str(frappe.utils.now_datetime()),
			"schema_version": 2,
			"standards": [dict(row) for row in standards],
			"parameters": [dict(row) for row in parameters],
		},
		default=str,
		sort_keys=True,
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
	selected_templates = resolve_activity_templates(crop_cycle, templates)
	for template in selected_templates:
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
	"""Initialize a missing current-stage pointer without advancing it.

	Stage advancement is an explicit Frappe Desk action implemented by
	``stage_progress.close_current_crop_cycle_stage``. Schedule generation may
	create or refresh stages, but must never close or advance an existing one.
	"""
	stages = frappe.get_all(
		"Crop Cycle Stage",
		filters={"crop_cycle": crop_cycle},
		fields=["name", "order_index", "start_date", "end_date", "status"],
		order_by="order_index asc",
	)
	if not stages:
		return
	existing_current = frappe.db.get_value("Crop Cycle", crop_cycle, "current_stage")
	if existing_current and any(row.name == existing_current for row in stages):
		return existing_current
	terminal_statuses = {"Completed", "Skipped", "Cancelled"}
	today = getdate(nowdate())
	current = next(
		(
			row
			for row in stages
			if row.status not in terminal_statuses
			and row.start_date
			and row.end_date
			and getdate(row.start_date) <= today <= getdate(row.end_date)
		),
		None,
	)
	if not current:
		current = next(
			(
				row for row in stages
				if row.status not in terminal_statuses
			),
			stages[-1],
		)
	frappe.db.set_value(
		"Crop Cycle",
		crop_cycle,
		"current_stage",
		current.name,
		update_modified=False,
	)
	if current.status == "Pending":
		frappe.db.set_value(
			"Crop Cycle Stage",
			current.name,
			"status",
			"In Progress",
			update_modified=False,
		)
	return current.name


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


def resolve_activity_templates(crop_cycle, templates):
	"""Resolve activities by exact/inherited recipe, then fall back to the same crop.

	Generic templates are always included. A same-crop fallback preserves shared activity
	formats when recipes only override quantities or stage timing.
	"""
	generic = [row for row in templates if not row.crop_recipe]
	recipe_chain = []
	seen = set()
	recipe = crop_cycle.recipe
	while recipe and recipe not in seen:
		seen.add(recipe)
		recipe_chain.append(recipe)
		recipe = frappe.db.get_value("Crop Recipe", recipe, "based_on_recipe")

	scoped = [row for row in templates if row.crop_recipe in recipe_chain]
	if scoped:
		return generic + scoped

	recipe_crops = {}
	for row in templates:
		if row.crop_recipe and row.crop_recipe not in recipe_crops:
			recipe_crops[row.crop_recipe] = frappe.db.get_value(
				"Crop Recipe", row.crop_recipe, "crop"
			)
	same_crop = [
		row
		for row in templates
		if row.crop_recipe and recipe_crops.get(row.crop_recipe) == crop_cycle.crop
	]
	return generic + same_crop
