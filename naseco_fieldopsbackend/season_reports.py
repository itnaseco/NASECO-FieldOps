import frappe
from frappe import _


def _filters(filters):
	filters = frappe._dict(filters or {})
	return {
		"season": filters.get("season") or "",
		"company": filters.get("company") or "",
		"today": frappe.utils.today(),
	}


def production_performance(filters=None):
	data = frappe.db.sql(
		"""
		select name, season, company, status, readiness_score,
			target_outgrowers, contracted_outgrowers,
			target_hectares, contracted_hectares, planted_hectares,
			planned_production_qty, forecast_production_qty, delivered_net_dry_qty,
			area_achievement_percent, production_achievement_percent,
			qa_coverage_percent, current_exposure_value, assessed_harvest_value,
			settled_net_payable
		from `tabSeason Production Plan`
		where docstatus < 2
			and (%(season)s = '' or season = %(season)s)
			and (%(company)s = '' or company = %(company)s)
		order by modified desc
		""",
		_filters(filters),
		as_dict=True,
	)
	return [
		_col("name", "Production Plan", "Link", "Season Production Plan", 170),
		_col("season", "Season", "Link", "Season", 100),
		_col("company", "Company", "Link", "Company", 150),
		_col("status", "Status", width=110),
		_col("readiness_score", "Readiness %", "Percent", width=105),
		_col("target_outgrowers", "Target Growers", "Int", width=110),
		_col("contracted_outgrowers", "Contracted Growers", "Int", width=130),
		_col("target_hectares", "Target Hectares", "Float", width=105),
		_col("contracted_hectares", "Contracted Hectares", "Float", width=120),
		_col("planted_hectares", "Planted Hectares", "Float", width=110),
		_col("area_achievement_percent", "Area Achievement %", "Percent", width=120),
		_col("planned_production_qty", "Planned Production", "Float", width=135),
		_col("forecast_production_qty", "Forecast Production", "Float", width=140),
		_col("delivered_net_dry_qty", "Delivered Net Qty", "Float", width=130),
		_col("production_achievement_percent", "Production %", "Percent", width=105),
		_col("qa_coverage_percent", "QA Coverage %", "Percent", width=110),
		_col("current_exposure_value", "Current Exposure", "Currency", width=130),
		_col("assessed_harvest_value", "Assessed Harvest", "Currency", width=130),
		_col("settled_net_payable", "Settled Payable", "Currency", width=125),
	], data


def grower_acreage(filters=None):
	data = frappe.db.sql(
		"""
		select coalesce(outgrower.region, 'Unassigned') region, contract.crop,
			contract.variety, contract.production_category,
			count(distinct contract.outgrower) contracted_outgrowers,
			count(distinct contract.farm_plot) contracted_plots,
			sum(contract.contracted_area_hectares) contracted_hectares,
			sum(contract.expected_yield_qty) forecast_qty,
			sum(contract.expected_harvest_value) forecast_value
		from `tabOutgrower Production Contract` contract
		left join `tabOutgrower` outgrower on outgrower.name = contract.outgrower
		where contract.docstatus = 1 and contract.status in ('Active', 'Fulfilled')
			and (%(season)s = '' or contract.season = %(season)s)
			and (%(company)s = '' or contract.company = %(company)s)
		group by coalesce(outgrower.region, 'Unassigned'), contract.crop,
			contract.variety, contract.production_category
		order by region, contract.crop, contract.variety
		""",
		_filters(filters),
		as_dict=True,
	)
	return [
		_col("region", "Region", "Link", "Region", 120),
		_col("crop", "Crop", "Link", "Crop", 100),
		_col("variety", "Variety", "Link", "Crop Variety", 120),
		_col("production_category", "Category", width=85),
		_col("contracted_outgrowers", "Growers", "Int", width=80),
		_col("contracted_plots", "Plots", "Int", width=70),
		_col("contracted_hectares", "Hectares", "Float", width=90),
		_col("forecast_qty", "Forecast Qty", "Float", width=110),
		_col("forecast_value", "Forecast Value", "Currency", width=125),
	], data


def agronomy_progress(filters=None):
	data = frappe.db.sql(
		"""
		select activity.assigned_to, stage.stage_name stage,
			count(*) scheduled,
			sum(activity.status = 'Completed') completed,
			sum(activity.status in ('Scheduled', 'In Progress')
				and activity.due_date < %(today)s) overdue,
			round(sum(activity.status = 'Completed') / count(*) * 100, 1) completion_percent
		from `tabStage Activity` activity
		inner join `tabCrop Cycle` cycle on cycle.name = activity.crop_cycle
		left join `tabCrop Cycle Stage` stage on stage.name = activity.stage
		where activity.status != 'Cancelled'
			and (%(season)s = '' or cycle.season = %(season)s)
			and (%(company)s = '' or cycle.company = %(company)s)
		group by activity.assigned_to, stage.stage_name, stage.order_index
		order by activity.assigned_to, stage.order_index
		""",
		_filters(filters),
		as_dict=True,
	)
	return [
		_col("assigned_to", "Outgrower Supervisor", "Link", "User", 180),
		_col("stage", "Crop Cycle Stage", width=150),
		_col("scheduled", "Scheduled", "Int", width=90),
		_col("completed", "Completed", "Int", width=90),
		_col("overdue", "Overdue", "Int", width=80),
		_col("completion_percent", "Completion %", "Percent", width=110),
	], data


def qa_coverage(filters=None):
	data = frappe.db.sql(
		"""
		select inspection.inspection_type, inspection.status,
			count(*) inspections,
			sum(inspection.status = 'Verified') verified,
			sum(inspection.status = 'Awaiting QA Review') awaiting_review,
			sum(inspection.status = 'Reinspection Required') reinspections,
			round(avg(inspection.farmer_compliance_percent), 1) farmer_compliance,
			round(avg(inspection.supervisor_compliance_percent), 1) supervisor_compliance,
			round(avg(inspection.spacing_compliance_percent), 1) spacing_compliance,
			round(avg(inspection.average_gps_accuracy_m), 1) gps_accuracy
		from `tabInspection` inspection
		inner join `tabCrop Cycle` cycle on cycle.name = inspection.crop_cycle
		where inspection.status != 'Cancelled'
			and (%(season)s = '' or inspection.season = %(season)s)
			and (%(company)s = '' or cycle.company = %(company)s)
		group by inspection.inspection_type, inspection.status
		order by inspection.inspection_type, inspection.status
		""",
		_filters(filters),
		as_dict=True,
	)
	return [
		_col("inspection_type", "Inspection Stage", width=140),
		_col("status", "Status", width=135),
		_col("inspections", "Inspections", "Int", width=90),
		_col("verified", "Verified", "Int", width=75),
		_col("awaiting_review", "Awaiting Review", "Int", width=110),
		_col("reinspections", "Reinspections", "Int", width=100),
		_col("farmer_compliance", "Farmer %", "Percent", width=90),
		_col("supervisor_compliance", "Supervisor %", "Percent", width=100),
		_col("spacing_compliance", "Spacing %", "Percent", width=90),
		_col("gps_accuracy", "GPS Accuracy (m)", "Float", width=110),
	], data


def inspector_performance(filters=None):
	data = frappe.db.sql(
		"""
		select inspection.assigned_to inspector,
			count(*) assigned_inspections,
			sum(inspection.status in ('Awaiting QA Review', 'Verified', 'Reinspection Required'))
				completed_inspections,
			sum(inspection.status = 'Verified') verified,
			sum(inspection.status = 'Reinspection Required') reinspections,
			sum(inspection.completed_take_count) inspection_takes,
			round(avg(inspection.spacing_compliance_percent), 1) spacing_compliance,
			round(avg(inspection.average_gps_accuracy_m), 1) gps_accuracy,
			round(avg(inspection.farmer_compliance_percent), 1) farmer_compliance,
			round(avg(inspection.supervisor_compliance_percent), 1) supervisor_compliance
		from `tabInspection` inspection
		inner join `tabCrop Cycle` cycle on cycle.name = inspection.crop_cycle
		where inspection.status != 'Cancelled'
			and (%(season)s = '' or inspection.season = %(season)s)
			and (%(company)s = '' or cycle.company = %(company)s)
		group by inspection.assigned_to
		order by completed_inspections desc
		""",
		_filters(filters),
		as_dict=True,
	)
	return [
		_col("inspector", "Quality Inspector", "Link", "User", 180),
		_col("assigned_inspections", "Assigned", "Int", width=80),
		_col("completed_inspections", "Completed", "Int", width=85),
		_col("verified", "Verified", "Int", width=75),
		_col("reinspections", "Reinspections", "Int", width=100),
		_col("inspection_takes", "Takes", "Int", width=70),
		_col("spacing_compliance", "Spacing %", "Percent", width=90),
		_col("gps_accuracy", "GPS Accuracy (m)", "Float", width=110),
		_col("farmer_compliance", "Farmer %", "Percent", width=90),
		_col("supervisor_compliance", "Supervisor %", "Percent", width=100),
	], data


def input_exposure(filters=None):
	data = frappe.db.sql(
		"""
		select cycle.name crop_cycle, plot.outgrower, cycle.plot, cycle.crop,
			cycle.expected_harvest_value, cycle.recoverable_stock_value,
			cycle.cash_advanced, cycle.pending_cash_advance, cycle.total_exposure,
			cycle.available_advance_capacity, cycle.forecast_net_payable,
			cycle.currency
		from `tabCrop Cycle` cycle
		left join `tabFarm Plot` plot on plot.name = cycle.plot
		where (%(season)s = '' or cycle.season = %(season)s)
			and (%(company)s = '' or cycle.company = %(company)s)
		order by cycle.total_exposure desc
		""",
		_filters(filters),
		as_dict=True,
	)
	return [
		_col("crop_cycle", "Crop Cycle", "Link", "Crop Cycle", 170),
		_col("outgrower", "Outgrower", "Link", "Outgrower", 160),
		_col("plot", "Farm Plot", "Link", "Farm Plot", 140),
		_col("crop", "Crop", "Link", "Crop", 90),
		_col("expected_harvest_value", "Expected Harvest", "Currency", "currency", 125),
		_col("recoverable_stock_value", "Stock Inputs", "Currency", "currency", 115),
		_col("cash_advanced", "Cash Advanced", "Currency", "currency", 115),
		_col("pending_cash_advance", "Pending Cash", "Currency", "currency", 110),
		_col("total_exposure", "Total Exposure", "Currency", "currency", 120),
		_col("available_advance_capacity", "Available Capacity", "Currency", "currency", 130),
		_col("forecast_net_payable", "Forecast Net", "Currency", "currency", 115),
		_col("currency", "Currency", "Link", "Currency", 70),
	], data


def harvest_settlement(filters=None):
	data = frappe.db.sql(
		"""
		select cycle.name crop_cycle, plot.outgrower, cycle.plot, cycle.crop,
			coalesce(quality.net_dry_qty, 0) net_dry_qty,
			coalesce(quality.harvest_value, 0) assessed_harvest_value,
			coalesce(quality.bonus, 0) potential_bonus,
			settlement.name settlement, settlement.status settlement_status,
			coalesce(settlement.stock_recovery_to_deduct, 0) stock_recovery,
			coalesce(settlement.cash_advance_to_allocate, 0) cash_recovery,
			coalesce(settlement.net_payable, 0) net_payable,
			coalesce(settlement.unrecovered_balance, 0) unrecovered_balance,
			coalesce(settlement.currency, cycle.currency) currency
		from `tabCrop Cycle` cycle
		left join `tabFarm Plot` plot on plot.name = cycle.plot
		left join (
			select crop_cycle,
				sum(case when disposition != 'Rejected' then net_dry_qty else 0 end) net_dry_qty,
				sum(provisional_payable_value) harvest_value,
				sum(potential_bonus_amount) bonus
			from `tabSeed Harvest Quality Assessment`
			where docstatus = 1 group by crop_cycle
		) quality on quality.crop_cycle = cycle.name
		left join `tabCrop Cycle Settlement` settlement
			on settlement.crop_cycle = cycle.name and settlement.docstatus < 2
		where (%(season)s = '' or cycle.season = %(season)s)
			and (%(company)s = '' or cycle.company = %(company)s)
		order by settlement.modified desc, cycle.modified desc
		""",
		_filters(filters),
		as_dict=True,
	)
	return [
		_col("crop_cycle", "Crop Cycle", "Link", "Crop Cycle", 170),
		_col("outgrower", "Outgrower", "Link", "Outgrower", 160),
		_col("plot", "Farm Plot", "Link", "Farm Plot", 140),
		_col("crop", "Crop", "Link", "Crop", 90),
		_col("net_dry_qty", "Net Dry Qty", "Float", width=105),
		_col("assessed_harvest_value", "Harvest Value", "Currency", "currency", 120),
		_col("potential_bonus", "Potential Bonus", "Currency", "currency", 115),
		_col("settlement", "Settlement", "Link", "Crop Cycle Settlement", 165),
		_col("settlement_status", "Status", width=105),
		_col("stock_recovery", "Stock Recovery", "Currency", "currency", 115),
		_col("cash_recovery", "Cash Recovery", "Currency", "currency", 115),
		_col("net_payable", "Net Payable", "Currency", "currency", 115),
		_col("unrecovered_balance", "Unrecovered", "Currency", "currency", 110),
		_col("currency", "Currency", "Link", "Currency", 70),
	], data


def _col(fieldname, label, fieldtype="Data", options=None, width=120):
	column = {
		"fieldname": fieldname,
		"label": _(label),
		"fieldtype": fieldtype,
		"width": width,
	}
	if options:
		column["options"] = options
	return column
