import frappe
from frappe import _
from frappe.utils import cint, flt

from naseco_fieldopsbackend.fieldops_finance import get_default_company


@frappe.whitelist()
def get_command_centre(plan=None, season=None):
	plan_name = plan or _find_plan(season)
	if not plan_name:
		return {"plan": None, "message": _("Create a Season Production Plan to begin.")}

	doc = frappe.get_doc("Season Production Plan", plan_name)
	doc.check_permission("read")
	doc.refresh_actuals()
	return {
		"plan": _plan_summary(doc),
		"targets": [_target_row(row) for row in doc.production_targets],
		"stages": _stage_progress(doc.season, doc.company),
		"quality": _quality_summary(doc.season, doc.company),
		"exposure": _exposure_by_region(doc.season, doc.company),
		"resources": [row.as_dict() for row in doc.resource_allocations if row.active],
		"milestones": [row.as_dict() for row in doc.milestones],
		"readiness": [row.as_dict() for row in doc.readiness_items],
		"reports": [
			"Season Production Performance",
			"Season Grower and Acreage Progress",
			"Season Agronomy Progress",
			"Season QA Coverage",
			"Season Inspector Performance",
			"Season Input and Exposure",
			"Season Harvest and Settlement",
		],
	}


def _find_plan(season=None):
	company = get_default_company()
	if season:
		return frappe.db.get_value(
			"Season Production Plan",
			{"season": season, "company": company, "docstatus": ["<", 2]},
			"name",
			order_by="modified desc",
		)
	return frappe.db.get_value(
		"Season Production Plan",
		{"company": company, "status": ["in", ["Active", "Approved", "Under Review", "Draft"]]},
		"name",
		order_by="modified desc",
	)


def _plan_summary(doc):
	fields = (
		"name",
		"plan_title",
		"season",
		"company",
		"status",
		"calendar_status",
		"readiness_score",
		"target_outgrowers",
		"contracted_outgrowers",
		"target_plots",
		"contracted_plots",
		"target_hectares",
		"contracted_hectares",
		"planted_hectares",
		"area_achievement_percent",
		"planned_production_qty",
		"forecast_production_qty",
		"delivered_net_dry_qty",
		"production_achievement_percent",
		"qa_coverage_percent",
		"current_exposure_value",
		"assessed_harvest_value",
		"settled_net_payable",
		"deferred_bonus_liability",
		"stock_coverage_percent",
		"planned_input_cost",
	)
	return {field: doc.get(field) for field in fields}


def _target_row(row):
	return {
		"region": row.region or _("All Regions"),
		"crop": row.crop,
		"variety": row.variety,
		"production_category": row.production_category,
		"target_outgrowers": cint(row.target_outgrowers),
		"target_hectares": flt(row.target_hectares),
		"planned_production_qty": flt(row.planned_production_qty),
	}


def _stage_progress(season, company):
	return frappe.db.sql(
		"""
		select
			coalesce(stage.stage_name, 'Not Started') stage,
			count(*) crop_cycles,
			coalesce(sum(contract.contracted_area_hectares), 0) hectares
		from `tabCrop Cycle` cycle
		left join `tabCrop Cycle Stage` stage on stage.name = cycle.current_stage
		left join `tabOutgrower Production Contract` contract
			on contract.name = cycle.production_contract
		where cycle.season = %(season)s and cycle.company = %(company)s
		group by coalesce(stage.stage_name, 'Not Started'), coalesce(stage.order_index, 0)
		order by coalesce(stage.order_index, 0)
		""",
		{"season": season, "company": company},
		as_dict=True,
	)


def _quality_summary(season, company):
	return frappe.db.sql(
		"""
		select
			status,
			count(*) inspection_count,
			round(avg(farmer_compliance_percent), 1) farmer_compliance,
			round(avg(supervisor_compliance_percent), 1) supervisor_compliance,
			round(avg(spacing_compliance_percent), 1) spacing_compliance,
			round(avg(average_gps_accuracy_m), 1) gps_accuracy
		from `tabInspection` inspection
		where inspection.season = %(season)s
			and exists (
				select 1 from `tabCrop Cycle` cycle
				where cycle.name = inspection.crop_cycle and cycle.company = %(company)s
			)
		group by status
		order by field(status, 'Awaiting QA Review', 'Reinspection Required',
			'In Progress', 'Scheduled', 'Verified', 'Cancelled')
		""",
		{"season": season, "company": company},
		as_dict=True,
	)


def _exposure_by_region(season, company):
	return frappe.db.sql(
		"""
		select
			coalesce(outgrower.region, 'Unassigned') region,
			count(*) crop_cycles,
			coalesce(sum(cycle.recoverable_stock_value), 0) stock_inputs,
			coalesce(sum(cycle.cash_advanced), 0) cash_advances,
			coalesce(sum(cycle.total_exposure), 0) total_exposure,
			coalesce(sum(cycle.forecast_net_payable), 0) forecast_net_payable
		from `tabCrop Cycle` cycle
		left join `tabFarm Plot` plot on plot.name = cycle.plot
		left join `tabOutgrower` outgrower on outgrower.name = plot.outgrower
		where cycle.season = %(season)s and cycle.company = %(company)s
		group by coalesce(outgrower.region, 'Unassigned')
		order by total_exposure desc
		""",
		{"season": season, "company": company},
		as_dict=True,
	)
