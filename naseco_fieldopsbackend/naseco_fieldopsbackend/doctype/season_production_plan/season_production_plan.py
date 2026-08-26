from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate

from naseco_fieldopsbackend.fieldops_finance import get_default_company, create_todo
from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe import get_recipe_variety_yield
from naseco_fieldopsbackend.seed_configuration import validate_seed_scope
from naseco_fieldopsbackend.roles import (
	FIELDOPS_FINANCE_APPROVER_ROLE,
	FIELDOPS_STORES_USER_ROLE,
	OUTGROWER_MANAGER_ROLE,
	OUTGROWER_SUPERVISOR_ROLE,
	QUALITY_INSPECTOR_ROLE,
	QUALITY_MANAGER_ROLE,
)
from naseco_fieldopsbackend.uom import get_item_uom_conversion


READINESS_ITEMS = (
	("Production Targets", "Regional crop and seed-category production targets approved"),
	("Growers and Plots", "Eligible grower and verified plot pipeline covers the target"),
	("Contracts and Pricing", "Contract templates and pricing policies approved"),
	("Crop Recipes", "Crop recipes and stage input rates approved"),
	("Quality Standards", "Inspection templates and compliance standards approved"),
	("Parent Seed and Inputs", "Parent seed and crop input availability reviewed"),
	("Warehouses", "Input source and harvest destination warehouses confirmed"),
	("Supervisor Capacity", "Outgrower Supervisor capacity allocated"),
	("Inspector Capacity", "Quality Inspector capacity allocated"),
	("Finance and Exposure", "Budget, cash flow and exposure ceiling reviewed"),
)

HECTARES_TO_ACRES = 2.47105381467
PER_HECTARE_TO_PER_ACRE = 0.40468564224


MILESTONES = (
	"Planning Approval",
	"Grower Contracting",
	"Parent Seed Allocation",
	"Input Procurement",
	"Planting",
	"Crop Emergence",
	"Vegetative",
	"Pre-flowering",
	"Flowering",
	"Pre-harvest",
	"Harvest",
	"Delivery",
	"Settlement",
	"Season Closure",
)

class SeasonProductionPlan(Document):
	def before_validate(self):
		self.set_defaults()
		self.initialize_controls()
		self.sync_target_recipe_yields()
		if self.docstatus == 0:
			self.sync_parent_seed_requirements()
		self.calculate_baseline()
		if self.docstatus == 0:
			self.sync_input_requirements()
		self.refresh_input_availability()
		self.calculate_readiness()
		self.refresh_actuals()

	def validate(self):
		self.validate_unique_plan()
		self.validate_governance_users()
		self.validate_targets()
		self.validate_resources()
		self.validate_milestones()
		if not 0 < flt(self.maximum_exposure_percent) <= 100:
			frappe.throw(_("Maximum Exposure % must be greater than zero and at most 100."))

	def before_submit(self):
		if not self.mandatory_readiness_complete:
			frappe.throw(
				_("All mandatory readiness items must be Ready or Not Applicable before approval.")
			)
		self.status = "Approved"

	def on_submit(self):
		self.create_management_todos()

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def set_defaults(self):
		self.company = self.company or get_default_company()
		self.plan_title = self.plan_title or (
			_("{0} Production Plan").format(self.season) if self.season else None
		)
		if self.season:
			self.calendar_status = frappe.db.get_value(
				"Season", self.season, "season_status"
			)
		try:
			settings = frappe.get_cached_doc("FieldOps Settings")
			self.finance_approver = self.finance_approver or settings.finance_approver
			self.stores_responsible = self.stores_responsible or settings.stores_approver
			self.maximum_exposure_percent = (
				self.maximum_exposure_percent
				or settings.maximum_exposure_percent
				or 70
			)
		except frappe.DoesNotExistError:
			pass

	def initialize_controls(self):
		if not self.readiness_items:
			for area, requirement in READINESS_ITEMS:
				responsible = self.outgrower_manager
				if area in ("Quality Standards", "Inspector Capacity"):
					responsible = self.quality_manager
				elif area == "Finance and Exposure":
					responsible = self.finance_approver
				elif area in ("Parent Seed and Inputs", "Warehouses"):
					responsible = self.stores_responsible
				self.append(
					"readiness_items",
					{
						"readiness_area": area,
						"requirement": requirement,
						"mandatory": 1,
						"responsible_user": responsible,
						"status": "Not Started",
					},
				)
		if not self.milestones and self.season:
			start_date, end_date = frappe.db.get_value(
				"Season", self.season, ["start_date", "end_date"]
			)
			for milestone in MILESTONES:
				self.append(
					"milestones",
					{
						"milestone": milestone,
						"planned_start_date": start_date,
						"planned_end_date": end_date,
						"status": "Not Started",
					},
				)

	def sync_target_recipe_yields(self):
		"""Snapshot recipe yield when a target first selects or changes its recipe."""
		for row in self.production_targets:
			if not row.crop_recipe:
				continue
			recipe_changed = row.yield_source_recipe != row.crop_recipe
			if not recipe_changed and row.recipe_yield_kg_per_hectare not in (None, ""):
				continue
			recipe_yield = get_recipe_variety_yield(frappe.get_doc("Crop Recipe", row.crop_recipe), getattr(row, "variety", None))
			row.recipe_yield_kg_per_hectare = flt(recipe_yield)
			row.yield_source_recipe = row.crop_recipe
			if recipe_changed or row.planned_yield_kg_per_hectare in (None, ""):
				row.planned_yield_kg_per_hectare = flt(recipe_yield)
				row.yield_override_reason = None

	def calculate_baseline(self):
		for row in self.production_targets:
			# Keep legacy acre values synchronized for existing reports and integrations.
			row.target_acres = flt(row.target_hectares) * HECTARES_TO_ACRES
			row.planned_yield_kg_per_acre = (
				flt(row.planned_yield_kg_per_hectare) * PER_HECTARE_TO_PER_ACRE
			)
			row.planned_production_qty = (
				flt(row.target_hectares) * flt(row.planned_yield_kg_per_hectare)
			)

		self.target_outgrowers = sum(cint(row.target_outgrowers) for row in self.production_targets)
		self.target_plots = sum(cint(row.target_plots) for row in self.production_targets)
		self.target_hectares = sum(flt(row.target_hectares) for row in self.production_targets)
		self.target_acres = sum(flt(row.target_acres) for row in self.production_targets)
		self.planned_production_qty = sum(
			flt(row.planned_production_qty) for row in self.production_targets
		)
		self.female_parent_seed_required_qty = sum(
			flt(row.required_stock_qty)
			for row in self.parent_seed_requirements
			if row.parent_role == "Female"
		)
		self.male_parent_seed_required_qty = sum(
			flt(row.required_stock_qty)
			for row in self.parent_seed_requirements
			if row.parent_role == "Male"
		)
		self.parent_seed_required_qty = sum(
			flt(row.required_stock_qty) for row in self.parent_seed_requirements
		)
		self.planned_input_cost = sum(
			flt(row.estimated_cost) for row in self.input_requirements
		)
		self.planned_supervisors = len(
			{
				row.user
				for row in self.resource_allocations
				if row.active and row.resource_role == OUTGROWER_SUPERVISOR_ROLE
			}
		)
		self.planned_inspectors = len(
			{
				row.user
				for row in self.resource_allocations
				if row.active and row.resource_role == QUALITY_INSPECTOR_ROLE
			}
		)

	def sync_parent_seed_requirements(self):
		"""Rebuild parent-seed demand from target hectares and recipe components."""
		self.set("parent_seed_requirements", [])
		for values in aggregate_parent_seed_requirements(self.production_targets):
			self.append("parent_seed_requirements", values)

	def sync_input_requirements(self):
		"""Rebuild derived demand while retaining user-entered planning details."""
		existing = {
			_input_requirement_key(row): {
				"estimated_rate": row.estimated_rate,
				"notes": row.notes,
			}
			for row in self.input_requirements
		}
		requirements = aggregate_input_requirements(self.production_targets, self.parent_seed_requirements)
		self.set("input_requirements", [])
		for values in requirements:
			preserved = existing.get(_input_requirement_key(values), {})
			self.append(
				"input_requirements",
				{
					**values,
					**preserved,
				},
			)

	def refresh_input_availability(self):
		required = available = 0
		for row in self.input_requirements:
			item = frappe.db.get_value(
				"Item",
				row.item_code,
				["stock_uom", "standard_rate"],
				as_dict=True,
			)
			if item:
				row.stock_uom = item.stock_uom
				row.estimated_rate = row.estimated_rate or item.standard_rate
			row.available_qty = get_available_stock(row.item_code, row.source_warehouse)
			row.shortage_qty = max(flt(row.required_qty) - flt(row.available_qty), 0)
			row.stock_coverage_percent = (
				min(flt(row.available_qty) / flt(row.required_qty) * 100, 100)
				if flt(row.required_qty)
				else 100
			)
			row.estimated_cost = flt(row.required_qty) * flt(row.estimated_rate)
			if row.material_request:
				row.procurement_status = "Material Request Created"
			elif row.shortage_qty:
				row.procurement_status = "Shortage Identified"
			else:
				row.procurement_status = "Available"
			required += flt(row.required_qty)
			available += min(flt(row.available_qty), flt(row.required_qty))
		self.stock_coverage_percent = available / required * 100 if required else 0
		self.planned_input_cost = sum(
			flt(row.estimated_cost) for row in self.input_requirements
		)

	def calculate_readiness(self):
		applicable = [
			row for row in self.readiness_items if row.status != "Not Applicable"
		]
		ready = [row for row in applicable if row.status == "Ready"]
		self.readiness_score = len(ready) / len(applicable) * 100 if applicable else 0
		self.mandatory_readiness_complete = int(
			all(
				not row.mandatory or row.status in ("Ready", "Not Applicable")
				for row in self.readiness_items
			)
		)

	def refresh_actuals(self):
		if not self.season or not self.company:
			return
		actuals = get_season_actuals(self.season, self.company)
		for fieldname, value in actuals.items():
			self.set(fieldname, value)
		self.area_achievement_percent = (
			flt(self.contracted_hectares) / flt(self.target_hectares) * 100
			if flt(self.target_hectares)
			else 0
		)
		self.production_achievement_percent = (
			flt(self.delivered_net_dry_qty) / flt(self.planned_production_qty) * 100
			if flt(self.planned_production_qty)
			else 0
		)
		self.forecast_variance_qty = (
			flt(self.forecast_production_qty) - flt(self.planned_production_qty)
		)
		self.refresh_resource_actuals()

	def refresh_resource_actuals(self):
		for row in self.resource_allocations:
			if row.resource_role == OUTGROWER_SUPERVISOR_ROLE:
				counts = frappe.db.sql(
					"""
					select
						count(*) assignments,
						sum(case when activity.status = 'Completed' then 1 else 0 end) completions
					from `tabStage Activity` activity
					inner join `tabCrop Cycle` cycle on cycle.name = activity.crop_cycle
					where cycle.season = %s and activity.assigned_to = %s
					""",
					(self.season, row.user),
					as_dict=True,
				)[0]
				row.actual_assignments = cint(counts.assignments)
				row.actual_completions = cint(counts.completions)
			else:
				row.actual_assignments = frappe.db.count(
					"Inspection",
					{"season": self.season, "assigned_to": row.user},
				)
				row.actual_completions = frappe.db.count(
					"Inspection",
					{
						"season": self.season,
						"assigned_to": row.user,
						"status": ["in", ["Awaiting QA Review", "Verified", "Completed"]],
					},
				)
			row.utilization_percent = (
				flt(row.actual_completions) / flt(row.actual_assignments) * 100
				if row.actual_assignments
				else 0
			)

	def validate_unique_plan(self):
		existing = frappe.db.get_value(
			"Season Production Plan",
			{
				"season": self.season,
				"company": self.company,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("Season Production Plan {0} already covers this Company and Season.").format(
					frappe.bold(existing)
				)
			)

	def validate_governance_users(self):
		for fieldname, role in (
			("outgrower_manager", OUTGROWER_MANAGER_ROLE),
			("quality_manager", QUALITY_MANAGER_ROLE),
			("finance_approver", FIELDOPS_FINANCE_APPROVER_ROLE),
			("stores_responsible", FIELDOPS_STORES_USER_ROLE),
		):
			user = self.get(fieldname)
			if user and role not in frappe.get_roles(user):
				frappe.throw(
					_("{0} must have the {1} role.").format(
						self.meta.get_label(fieldname), role
					)
				)

	def validate_targets(self):
		if not self.production_targets:
			frappe.throw(_("At least one production target is required."))
		season_dates = frappe.db.get_value(
			"Season", self.season, ["start_date", "end_date"], as_dict=True
		)
		seen = set()
		for row in self.production_targets:
			validate_seed_scope(
				row.production_category, row.seed_class,
				_("Production target row {0}").format(row.idx),
			)
			key = (
				row.region, row.location, row.outgrower_supervisor,
				row.crop, row.variety, row.production_category, row.seed_class,
			)
			if key in seen:
				frappe.throw(_("Production target row {0} duplicates another target.").format(row.idx))
			seen.add(key)
			if flt(row.target_hectares) <= 0:
				frappe.throw(_("Target Hectares must be greater than zero in row {0}.").format(row.idx))
			if self.docstatus == 1 and flt(row.recipe_yield_kg_per_hectare) <= 0:
				frappe.throw(
					_("The selected Crop Recipe must define a positive Expected Yield (Kg/Ha) before submitting row {0}.").format(row.idx)
				)
			if self.docstatus == 1 and flt(row.planned_yield_kg_per_hectare) <= 0:
				frappe.throw(
					_("Planned Yield (Kg/Ha) must be greater than zero before submitting row {0}.").format(row.idx)
				)
			if (
				self.docstatus == 1
				and abs(flt(row.planned_yield_kg_per_hectare) - flt(row.recipe_yield_kg_per_hectare)) > 0.01
				and not (row.yield_override_reason or "").strip()
			):
				frappe.throw(_("A Yield Override Reason is required in row {0}.").format(row.idx))
			if not frappe.db.get_value("User", row.outgrower_supervisor, "enabled"):
				frappe.throw(_("Outgrower Supervisor in row {0} must be an enabled user.").format(row.idx))
			if OUTGROWER_SUPERVISOR_ROLE not in frappe.get_roles(row.outgrower_supervisor):
				frappe.throw(_("Outgrower Supervisor in row {0} must have the {1} role.").format(
					row.idx, OUTGROWER_SUPERVISOR_ROLE
				))
			if row.variety and frappe.db.get_value("Crop Variety", row.variety, "crop") != row.crop:
				frappe.throw(_("Variety must belong to the target Crop in row {0}.").format(row.idx))
			recipe = frappe.get_doc("Crop Recipe", row.crop_recipe)
			if recipe.crop != row.crop:
				frappe.throw(_("Crop Recipe must belong to the target Crop in row {0}.").format(row.idx))
			if get_recipe_variety_yield(recipe, row.variety) is None:
				frappe.throw(_("Crop Recipe does not apply to the target Variety in row {0}.").format(row.idx))
			if (
				getdate(row.planting_window_from) < getdate(season_dates.start_date)
				or getdate(row.planting_window_to) > getdate(season_dates.end_date)
				or getdate(row.planting_window_from) > getdate(row.planting_window_to)
			):
				frappe.throw(_("Planting window in row {0} must fall within the Season.").format(row.idx))

	def validate_resources(self):
		seen = set()
		for row in self.resource_allocations:
			if (row.resource_role, row.user) in seen:
				frappe.throw(_("User {0} is allocated more than once for {1}.").format(row.user, row.resource_role))
			seen.add((row.resource_role, row.user))
			if row.resource_role not in frappe.get_roles(row.user):
				frappe.throw(_("{0} does not have the {1} role.").format(row.user, row.resource_role))

	def validate_milestones(self):
		for row in self.milestones:
			if getdate(row.planned_start_date) > getdate(row.planned_end_date):
				frappe.throw(_("Milestone start cannot be after its end in row {0}.").format(row.idx))

	def create_management_todos(self):
		for user, description in (
			(self.outgrower_manager, f"Activate contracting for {self.season}"),
			(self.quality_manager, f"Confirm QA assignments for {self.season}"),
			(self.finance_approver, f"Monitor seasonal exposure for {self.season}"),
			(self.stores_responsible, f"Resolve input shortages for {self.season}"),
		):
			create_todo(user, self.doctype, self.name, description, nowdate(), "High")


def get_available_stock(item_code, warehouse=None):
	if not item_code:
		return 0
	filters = {"item_code": item_code}
	if warehouse:
		filters["warehouse"] = warehouse
	return flt(frappe.db.get_value("Bin", filters, "actual_qty") or 0)


def get_season_actuals(season, company):
	contracts = frappe.db.sql(
		"""
		select
			count(distinct outgrower) contracted_outgrowers,
			count(distinct farm_plot) contracted_plots,
			coalesce(sum(contracted_area_hectares), 0) contracted_hectares,
			coalesce(sum(expected_yield_qty), 0) forecast_production_qty
		from `tabOutgrower Production Contract`
		where season = %(season)s and company = %(company)s and docstatus = 1
			and status in ('Active', 'Fulfilled')
		""",
		{"season": season, "company": company},
		as_dict=True,
	)[0]
	planted_hectares = flt(
		frappe.db.sql(
			"""
			select coalesce(sum(lot.area_hectares), 0)
			from `tabCrop Production Lot` lot
			inner join `tabCrop Cycle` cycle on cycle.name = lot.crop_cycle
			where cycle.season = %s and cycle.company = %s
				and lot.status != 'Rejected'
			""",
			(season, company),
		)[0][0]
	)
	inspection = frappe.db.sql(
		"""
		select
			count(*) total_inspection_count,
			sum(case when status in ('Verified', 'Completed') then 1 else 0 end)
				verified_inspection_count
		from `tabInspection`
		where season = %(season)s
			and exists (
				select 1 from `tabCrop Cycle` cycle
				where cycle.name = `tabInspection`.crop_cycle
					and cycle.company = %(company)s
			)
		""",
		{"season": season, "company": company},
		as_dict=True,
	)[0]
	harvest = frappe.db.sql(
		"""
		select
			coalesce(sum(case when disposition != 'Rejected' then net_dry_qty else 0 end), 0)
				delivered_net_dry_qty,
			coalesce(sum(provisional_payable_value), 0) assessed_harvest_value,
			coalesce(sum(potential_bonus_amount), 0) deferred_bonus_liability
		from `tabSeed Harvest Quality Assessment`
		where season = %s and docstatus = 1
			and crop_cycle in (
				select name from `tabCrop Cycle` where company = %s
			)
		""",
		(season, company),
		as_dict=True,
	)[0]
	finance = frappe.db.sql(
		"""
		select
			coalesce(sum(recoverable_stock_value), 0) recoverable_input_value,
			coalesce(sum(cash_advanced), 0) cash_advance_value
		from `tabCrop Cycle`
		where season = %(season)s and company = %(company)s
		""",
		{"season": season, "company": company},
		as_dict=True,
	)[0]
	settlements = frappe.db.sql(
		"""
		select
			coalesce(sum(net_payable), 0) settled_net_payable
		from `tabCrop Cycle Settlement`
		where company = %(company)s and docstatus = 1
			and crop_cycle in (
				select name from `tabCrop Cycle` where season = %(season)s
			)
		""",
		{"season": season, "company": company},
	)[0][0]
	total_inspections = cint(inspection.total_inspection_count)
	verified = cint(inspection.verified_inspection_count)
	return frappe._dict(
		**contracts,
		planted_hectares=planted_hectares,
		total_inspection_count=total_inspections,
		verified_inspection_count=verified,
		qa_coverage_percent=verified / total_inspections * 100 if total_inspections else 0,
		**harvest,
		**finance,
		current_exposure_value=flt(finance.recoverable_input_value) + flt(finance.cash_advance_value),
		settled_net_payable=flt(settlements),
	)


def aggregate_parent_seed_requirements(production_targets):
	"""Calculate every recipe parent-seed component required by production targets."""
	requirements = {}
	for target in production_targets:
		if not target.crop_recipe or flt(target.target_hectares) <= 0:
			continue
		recipe = frappe.get_doc("Crop Recipe", target.crop_recipe)
		all_parent_items = list(recipe.parent_seed_items or [])
		variety_items = [item for item in all_parent_items if getattr(item, "variety", None) == getattr(target, "variety", None)]
		parent_items = variety_items or [item for item in all_parent_items if not getattr(item, "variety", None)]
		for item in parent_items:
			conversion = get_item_uom_conversion(item.item_code, item.uom)
			key = (
				target.crop_recipe, item.ratio_group, item.parent_role, flt(item.ratio_value),
				item.item_code, conversion.uom, conversion.stock_uom, item.source_warehouse,
				item.recovery_policy or "Fully Recoverable", flt(item.recoverable_percent),
			)
			values = requirements.setdefault(
				key,
				{
					"crop_recipe": target.crop_recipe,
					"ratio_group": item.ratio_group,
					"parent_role": item.parent_role,
					"ratio_value": flt(item.ratio_value),
					"item_code": item.item_code,
					"target_hectares": 0,
					"quantity_per_hectare": flt(item.quantity_per_hectare),
					"uom": conversion.uom,
					"conversion_factor": flt(conversion.conversion_factor),
					"required_qty": 0,
					"stock_uom": conversion.stock_uom,
					"required_stock_qty": 0,
					"source_warehouse": item.source_warehouse,
					"recovery_policy": item.recovery_policy or "Fully Recoverable",
					"recoverable_percent": flt(item.recoverable_percent),
				},
			)
			required_qty = flt(target.target_hectares) * flt(item.quantity_per_hectare)
			values["target_hectares"] += flt(target.target_hectares)
			values["required_qty"] += required_qty
			values["required_stock_qty"] += required_qty * flt(conversion.conversion_factor)

	return [requirements[key] for key in sorted(
		requirements, key=lambda key: tuple(str(value or "") for value in key)
	)]


def _input_requirement_key(row):
	get_value = row.get if hasattr(row, "get") else lambda fieldname: getattr(row, fieldname, None)
	return (
		get_value("item_code"),
		get_value("source_warehouse"),
		get_value("recovery_policy") or "Fully Recoverable",
		flt(get_value("recoverable_percent")),
	)


def aggregate_input_requirements(production_targets, parent_seed_requirements=None):
	"""Calculate stock demand from target hectares and their selected recipes."""
	requirements = defaultdict(float)
	for parent_seed in parent_seed_requirements or []:
		key = (
			parent_seed.item_code, parent_seed.source_warehouse,
			parent_seed.recovery_policy or "Fully Recoverable",
			flt(parent_seed.recoverable_percent),
		)
		requirements[key] += flt(parent_seed.required_stock_qty)

	for target in production_targets:
		if not target.crop_recipe:
			continue
		recipe = frappe.get_doc("Crop Recipe", target.crop_recipe)
		# Current recipes keep inputs on the recipe. Retain compatibility with
		# earlier recipes that nested them under stages.
		recipe_inputs = list(recipe.inputs or [])
		if not recipe_inputs:
			recipe_inputs = [item for stage in recipe.stages or [] for item in stage.inputs or []]
		for item in recipe_inputs:
			if item.resource_type != "Stock Item" or not item.item_code:
				continue
			key = (
				item.item_code,
				item.source_warehouse,
				item.recovery_policy or "Fully Recoverable",
				flt(item.recoverable_percent),
			)
			qty_per_hectare = flt(
				item.stock_quantity_per_hectare
				or flt(item.quantity_per_hectare) * (flt(item.conversion_factor) or 1)
			)
			requirements[key] += flt(target.target_hectares) * qty_per_hectare

	return [
		{
			"item_code": item_code,
			"required_qty": required_qty,
			"source_warehouse": warehouse,
			"recovery_policy": recovery_policy,
			"recoverable_percent": recoverable_percent,
		}
		for (item_code, warehouse, recovery_policy, recoverable_percent), required_qty in sorted(
			requirements.items(), key=lambda entry: tuple(str(value or "") for value in entry[0])
		)
	]


@frappe.whitelist()
def generate_input_requirements(plan):
	doc = frappe.get_doc("Season Production Plan", plan)
	if doc.docstatus != 0:
		frappe.throw(_("Input requirements can only be regenerated on a draft plan."))
	doc.sync_parent_seed_requirements()
	doc.calculate_baseline()
	doc.sync_input_requirements()
	doc.save(ignore_permissions=True)
	return doc.name

@frappe.whitelist()
def refresh_plan_actuals(plan):
	doc = frappe.get_doc("Season Production Plan", plan)
	doc.refresh_actuals()
	values = {
		fieldname: doc.get(fieldname)
		for fieldname in (
			"contracted_outgrowers",
			"contracted_plots",
			"contracted_hectares",
			"planted_hectares",
			"forecast_production_qty",
			"delivered_net_dry_qty",
			"verified_inspection_count",
			"total_inspection_count",
			"qa_coverage_percent",
			"recoverable_input_value",
			"cash_advance_value",
			"current_exposure_value",
			"assessed_harvest_value",
			"settled_net_payable",
			"deferred_bonus_liability",
			"area_achievement_percent",
			"production_achievement_percent",
			"forecast_variance_qty",
		)
	}
	frappe.db.set_value(doc.doctype, doc.name, values, update_modified=False)
	for row in doc.resource_allocations:
		frappe.db.set_value(
			row.doctype,
			row.name,
			{
				"actual_assignments": row.actual_assignments,
				"actual_completions": row.actual_completions,
				"utilization_percent": row.utilization_percent,
			},
			update_modified=False,
		)
	return values


@frappe.whitelist()
def create_shortage_material_request(plan):
	doc = frappe.get_doc("Season Production Plan", plan)
	if doc.docstatus != 1:
		frappe.throw(_("Approve the Season Production Plan before procuring shortages."))
	items = []
	for row in doc.input_requirements:
		if flt(row.shortage_qty) <= 0 or row.material_request:
			continue
		items.append(
			{
				"item_code": row.item_code,
				"qty": row.shortage_qty,
				"schedule_date": nowdate(),
				"warehouse": row.source_warehouse,
				"uom": row.stock_uom,
			}
		)
	if not items:
		frappe.throw(_("There are no unrequested input shortages."))
	request = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": doc.company,
			"transaction_date": nowdate(),
			"schedule_date": nowdate(),
			"title": f"Season inputs for {doc.season}",
			"items": items,
		}
	).insert(ignore_permissions=True)
	for row in doc.input_requirements:
		if flt(row.shortage_qty) > 0 and not row.material_request:
			frappe.db.set_value(
				row.doctype,
				row.name,
				{
					"material_request": request.name,
					"procurement_status": "Material Request Created",
				},
				update_modified=False,
			)
	create_todo(
		doc.stores_responsible,
		"Material Request",
		request.name,
		f"Review season input shortages for {doc.season}",
		nowdate(),
		"High",
	)
	return request.name
