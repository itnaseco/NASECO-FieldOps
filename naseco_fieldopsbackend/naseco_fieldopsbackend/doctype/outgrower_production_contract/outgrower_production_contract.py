# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime

from naseco_fieldopsbackend.fieldops_finance import (
	ensure_outgrower_supplier,
	get_default_company,
	require_outgrower_manager,
)
from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season import get_season_for_date
from naseco_fieldopsbackend.seed_configuration import get_variety_seed_item, validate_seed_scope


class OutgrowerProductionContract(Document):
	def before_validate(self):
		self.set_party_context()
		self.set_season_from_planting_date()
		self.resolve_crop_recipe()
		self.apply_contract_template()
		self.capture_legal_snapshot()
		self.initialize_signatories()
		self.apply_pricing_policy()
		self.apply_variety_seed_items()
		self.initialize_parent_seed_items()
		self.calculate_contract_values()
		self.company_obligations = self.company_obligations or _(
			"<p>Provide contracted technical support, inspections, collection and payment.</p>"
		)

	def validate(self):
		validate_seed_scope(self.production_category, self.seed_class)
		self.validate_plot()
		self.validate_crop_scope()
		self.validate_contract_template()
		self.validate_pricing_policy()
		self.validate_dates()
		self.validate_season()
		self.validate_commercial_terms()
		self.validate_parent_seed_items()
		self.validate_quality_terms()
		self.validate_contracted_area()

	def before_submit(self):
		require_outgrower_manager()
		self.validate_outgrower_eligibility()
		self.sync_optional_signatures()
		self.validate_no_active_contract()
		self.status = "Active"

	def before_cancel(self):
		if self.linked_crop_cycle and frappe.db.exists("Crop Cycle", self.linked_crop_cycle):
			frappe.throw(
				_("Contract {0} cannot be cancelled while Crop Cycle {1} is linked.").format(
					frappe.bold(self.name),
					frappe.bold(self.linked_crop_cycle),
				)
			)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def set_party_context(self):
		if self.farm_plot:
			plot_outgrower = frappe.db.get_value("Farm Plot", self.farm_plot, "outgrower")
			self.outgrower = self.outgrower or plot_outgrower
		if self.outgrower:
			self.supplier = frappe.db.get_value("Outgrower", self.outgrower, "supplier")
		if not self.company:
			self.company = get_default_company()
		if self.company:
			self.currency = frappe.db.get_value("Company", self.company, "default_currency")

	def resolve_crop_recipe(self):
		if self.crop_recipe or not self.crop:
			return
		from naseco_fieldopsbackend.recipe_planning import resolve_recipe

		self.crop_recipe = resolve_recipe(
			self.crop, self.variety, self.outgrower, self.company, self.agreement_date
		)

	def apply_contract_template(self):
		if not self.contract_template or self.docstatus != 0:
			return
		template = frappe.get_doc("Production Contract Template", self.contract_template)
		self.template_version = template.template_version
		self.pricing_policy = template.pricing_policy
		self.production_category = self.production_category or template.production_category
		self.seed_class = self.seed_class or template.seed_class
		self.agreement_title = template.agreement_title
		self.seed_handbook_reference = template.seed_handbook_reference
		self.legal_reference = template.legal_reference
		self.company_obligations = template.company_responsibilities
		self.farmer_obligations = template.farmer_responsibilities
		self.supervisor_obligations = template.supervisor_responsibilities
		self.quality_standard_terms = template.quality_terms
		self.input_recovery_terms = template.input_recovery_terms
		self.termination_terms = template.termination_terms

	def apply_variety_seed_items(self):
		if self.docstatus != 0:
			return
		self.harvest_item = self.harvest_item or get_variety_seed_item(
			self.variety, self.production_category, self.seed_class, "Raw Seed"
		)
		self.parent_seed_item = self.parent_seed_item or get_variety_seed_item(
			self.variety, self.production_category, self.seed_class, "Parent Seed"
		)

	def capture_legal_snapshot(self):
		if self.docstatus != 0:
			return
		if self.outgrower:
			outgrower = frappe.db.get_value(
				"Outgrower",
				self.outgrower,
				[
					"full_name",
					"national_id",
					"phone",
					"village",
					"sub_county",
					"district",
					"assigned_supervisor",
				],
				as_dict=True,
			)
			if outgrower:
				self.grower_name_snapshot = outgrower.full_name
				self.national_id_snapshot = outgrower.national_id
				self.phone_snapshot = outgrower.phone
				self.village_snapshot = outgrower.village
				self.sub_county_snapshot = outgrower.sub_county
				self.district_snapshot = outgrower.district
				self.supervisor_snapshot = outgrower.assigned_supervisor
		if self.farm_plot:
			plot = frappe.db.get_value(
				"Farm Plot",
				self.farm_plot,
				["plot_id", "area_hectares", "area_acres", "geojson"],
				as_dict=True,
			)
			if plot:
				self.plot_id_snapshot = plot.plot_id
				self.plot_geojson_snapshot = plot.geojson
				self.contracted_area_hectares = self.contracted_area_hectares or plot.area_hectares or (flt(plot.area_acres) * 0.40468564224)
				self.contracted_area_acres = self.contracted_area_acres or (flt(self.contracted_area_hectares) * 2.47105381467)

	def apply_pricing_policy(self):
		if not self.pricing_policy:
			return
		policy = frappe.get_doc("Outgrower Pricing Policy", self.pricing_policy)
		self.pricing_policy_version = policy.policy_version
		self.quota_kg_per_hectare = flt(policy.get("quota_kg_per_hectare")) or (
			flt(policy.get("quota_kg_per_acre")) * 2.47105381467
		)
		self.quota_kg_per_acre = flt(self.quota_kg_per_hectare) * 0.40468564224
		self.pricing_method = "Formula"
		self.pricing_formula = (
			f"Versioned yield and genetic-purity bands from pricing policy {policy.name}."
		)
		self.contract_rate = policy.advance_valuation_rate
		self.currency = policy.currency

	def initialize_signatories(self):
		if not self.contract_template or self.docstatus != 0:
			return
		existing_roles = {row.signatory_role for row in self.signatories}
		for role in (
			"Outgrower",
			"Outgrower Manager",
			"Witness",
			"Outgrower Supervisor",
		):
			if role in existing_roles:
				continue
			values = {"signatory_role": role}
			if role == "Outgrower":
				values.update(
					{
						"full_name": self.grower_name_snapshot,
						"phone": self.phone_snapshot,
					}
				)
			elif role == "Outgrower Supervisor" and self.supervisor_snapshot:
				values.update(
					{
						"user": self.supervisor_snapshot,
						"full_name": frappe.db.get_value(
							"User", self.supervisor_snapshot, "full_name"
						)
						or self.supervisor_snapshot,
						"phone": frappe.db.get_value(
							"User", self.supervisor_snapshot, "mobile_no"
						),
					}
				)
			self.append("signatories", values)

	def initialize_parent_seed_items(self):
		if self.docstatus != 0 or self.parent_seed_items:
			return
		if self.crop_recipe:
			recipe = frappe.get_doc("Crop Recipe", self.crop_recipe)
			for source in recipe.parent_seed_items or []:
				self.append("parent_seed_items", {
					"parent_role": source.parent_role,
					"item": source.item_code,
					"uom": source.stock_uom or source.uom,
					"quantity_kg_per_hectare": source.quantity_per_hectare,
					"rate": frappe.db.get_value("Item", source.item_code, "standard_rate"),
				})
			if self.parent_seed_items:
				return
		if not self.parent_seed_item:
			return
		area = flt(self.contracted_area_hectares) or (flt(self.contracted_area_acres) * 0.40468564224)
		self.append("parent_seed_items", {
			"parent_role": "Other",
			"item": self.parent_seed_item,
			"uom": self.parent_seed_uom,
			"quantity_kg_per_hectare": flt(self.planned_parent_seed_qty) / area if area else 0,
			"rate": self.parent_seed_rate,
		})

	def validate_parent_seed_items(self):
		seen = set()
		for row in self.parent_seed_items or []:
			key = (row.parent_role, row.item)
			if key in seen:
				frappe.throw(_("Parent Seed Item {0} is duplicated for role {1}.").format(row.item, row.parent_role))
			seen.add(key)
			if flt(row.quantity_kg_per_hectare) <= 0:
				frappe.throw(_("Parent seed quantity per hectare must be greater than zero."))

	def calculate_contract_values(self):
		if not flt(self.contracted_area_hectares) and flt(self.contracted_area_acres):
			self.contracted_area_hectares = flt(self.contracted_area_acres) * 0.40468564224
		if not flt(self.quota_kg_per_hectare) and flt(self.quota_kg_per_acre):
			self.quota_kg_per_hectare = flt(self.quota_kg_per_acre) * 2.47105381467
		if self.variety:
			self.expected_yield_kg_per_hectare = flt(frappe.db.get_value("Crop Variety", self.variety, "expected_yield_kg_per_hectare"))
		self.contracted_quota_qty = flt(self.contracted_area_hectares) * flt(self.quota_kg_per_hectare)
		if self.expected_yield_kg_per_hectare:
			self.expected_yield_qty = flt(self.contracted_area_hectares) * flt(self.expected_yield_kg_per_hectare)
		elif self.pricing_policy and not flt(self.expected_yield_qty):
			self.expected_yield_qty = self.contracted_quota_qty
		self.expected_harvest_value = flt(self.expected_yield_qty) * flt(self.contract_rate)
		if self.parent_seed_items:
			for row in self.parent_seed_items:
				row.planned_quantity = flt(row.quantity_kg_per_hectare) * flt(self.contracted_area_hectares)
				row.amount = flt(row.planned_quantity) * flt(row.rate)
			self.planned_parent_seed_qty = sum(flt(row.planned_quantity) for row in self.parent_seed_items)
			self.planned_parent_seed_value = sum(flt(row.amount) for row in self.parent_seed_items)
		else:
			self.planned_parent_seed_value = flt(self.planned_parent_seed_qty) * flt(self.parent_seed_rate)

	def validate_plot(self):
		if not self.farm_plot:
			return
		plot = frappe.db.get_value(
			"Farm Plot",
			self.farm_plot,
			["outgrower", "status"],
			as_dict=True,
		)
		if not plot or plot.outgrower != self.outgrower:
			frappe.throw(_("Farm Plot must belong to the selected Outgrower."))
		if plot.status and plot.status != "Active":
			frappe.throw(_("Only an active Farm Plot can be contracted."))
		if not self.supplier:
			frappe.throw(
				_("Create the Supplier for Outgrower {0} before submitting this contract.").format(
					frappe.bold(self.outgrower)
				)
			)

	def validate_crop_scope(self):
		if self.variety:
			variety_crop = frappe.db.get_value("Crop Variety", self.variety, "crop")
			if variety_crop and variety_crop != self.crop:
				frappe.throw(_("Crop Variety must belong to the selected Crop."))
		if self.crop_recipe:
			recipe_crop = frappe.db.get_value("Crop Recipe", self.crop_recipe, "crop")
			if recipe_crop and recipe_crop != self.crop:
				frappe.throw(_("Crop Recipe must belong to the selected Crop."))

	def validate_contract_template(self):
		if not self.contract_template:
			return
		template = frappe.db.get_value(
			"Production Contract Template",
			self.contract_template,
			["season", "crop", "production_category", "seed_class", "pricing_policy", "docstatus", "status"],
			as_dict=True,
		)
		if not template or template.docstatus != 1 or template.status != "Active":
			frappe.throw(_("Contract Template must be submitted and active."))
		for fieldname in ("season", "crop", "production_category", "seed_class"):
			if self.get(fieldname) != template.get(fieldname):
				frappe.throw(
					_("Contract {0} must match the selected Contract Template.").format(
						self.meta.get_label(fieldname)
					)
				)
		if self.pricing_policy != template.pricing_policy:
			frappe.throw(_("Pricing Policy must be the policy approved on the Contract Template."))

	def validate_pricing_policy(self):
		if not self.pricing_policy:
			return
		policy = frappe.db.get_value(
			"Outgrower Pricing Policy",
			self.pricing_policy,
			["season", "crop", "production_category", "seed_class", "docstatus", "status"],
			as_dict=True,
		)
		if not policy or policy.docstatus != 1 or policy.status != "Active":
			frappe.throw(_("Pricing Policy must be submitted and active."))
		for fieldname in ("season", "crop", "production_category", "seed_class"):
			if self.get(fieldname) != policy.get(fieldname):
				frappe.throw(
					_("Contract {0} must match the selected Pricing Policy.").format(
						self.meta.get_label(fieldname)
					)
				)

	def validate_dates(self):
		date_order = [
			("Contract Start Date", self.contract_start_date),
			("Planting Window From", self.planting_start_date),
			("Planting Window To", self.planting_end_date),
			("Expected Harvest Date", self.expected_harvest_date),
			("Contract End Date", self.contract_end_date),
		]
		for (left_label, left), (right_label, right) in zip(date_order, date_order[1:]):
			if left and right and getdate(left) > getdate(right):
				frappe.throw(_("{0} cannot be after {1}.").format(left_label, right_label))

	def set_season_from_planting_date(self):
		if self.season or not self.planting_start_date:
			return

		season = get_season_for_date(self.planting_start_date)
		if season:
			self.season = season.name

	def validate_season(self):
		if not self.season or not self.planting_start_date or not self.planting_end_date:
			return
		if self.has_unchanged_submitted_season_scope():
			return

		season_dates = frappe.db.get_value(
			"Season",
			self.season,
			["start_date", "end_date"],
			as_dict=True,
		)
		if not season_dates or not season_dates.start_date or not season_dates.end_date:
			frappe.throw(_("The selected Season must have a valid Start Date and End Date."))

		if not is_planting_window_within_season(
			season_dates.start_date,
			season_dates.end_date,
			self.planting_start_date,
			self.planting_end_date,
		):
			frappe.throw(
				_(
					"Planting Window From and Planting Window To must fall within Season {0} ({1} to {2})."
				).format(
					frappe.bold(self.season),
					frappe.format_value(season_dates.start_date, {"fieldtype": "Date"}),
					frappe.format_value(season_dates.end_date, {"fieldtype": "Date"}),
				)
			)

	def has_unchanged_submitted_season_scope(self):
		previous = self.get_doc_before_save()
		if self.docstatus != 1 or not previous or previous.docstatus != 1:
			return False

		return all(
			self.get(fieldname) == previous.get(fieldname)
			for fieldname in ("season", "planting_start_date", "planting_end_date")
		)

	def validate_commercial_terms(self):
		if flt(self.expected_yield_qty) <= 0:
			frappe.throw(_("Expected Harvest Quantity must be greater than zero."))
		if flt(self.contract_rate) <= 0:
			frappe.throw(_("Agreed Operational Rate must be greater than zero."))
		if not 0 < flt(self.max_exposure_percent) <= 100:
			frappe.throw(_("Maximum Exposure % must be greater than zero and at most 100."))
		if self.pricing_method == "Formula" and not self.pricing_formula:
			frappe.throw(_("Pricing Formula is required when Pricing Method is Formula."))

	def validate_contracted_area(self):
		if flt(self.contracted_area_hectares) <= 0:
			frappe.throw(_("Contracted Area must be greater than zero."))
		if not self.farm_plot:
			return
		plot_area = flt(frappe.db.get_value("Farm Plot", self.farm_plot, "area_hectares"))
		if plot_area and flt(self.contracted_area_hectares) > plot_area:
			frappe.throw(
				_("Contracted Area cannot exceed the Farm Plot area of {0} hectares.").format(plot_area)
			)

	def validate_outgrower_eligibility(self):
		eligibility = frappe.db.get_value("Outgrower", self.outgrower, "eligibility_status")
		if eligibility == "Ineligible":
			frappe.throw(_("This Outgrower is ineligible for a new production contract."))
		if eligibility != "Under Review":
			return
		if not self.eligibility_override_reason:
			frappe.throw(_("An Eligibility Override Reason is required for an Outgrower under review."))
		if frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
			frappe.throw(
				_("Only a System Manager can approve an eligibility override."),
				frappe.PermissionError,
			)
		self.eligibility_override_approved_by = frappe.session.user

	def sync_optional_signatures(self):
		signed_rows = [
			row
			for row in self.signatories
			if row.full_name and row.signature and row.signed_at
		]
		if not signed_rows:
			return

		self.is_signed = 1
		self.signed_on = max(row.signed_at for row in signed_rows)
		manager = next(
			(row for row in signed_rows if row.signatory_role == "Outgrower Manager"),
			None,
		)
		self.company_signatory = manager.user if manager and manager.user else self.company_signatory

	def validate_quality_terms(self):
		for label, value in (
			(_("Minimum Farmer Compliance %"), self.minimum_farmer_compliance_percent),
			(_("Minimum Supervisor Compliance %"), self.minimum_supervisor_compliance_percent),
		):
			if not 0 <= flt(value) <= 100:
				frappe.throw(_("{0} must be between zero and 100.").format(label))
		if flt(self.target_take_spacing_m) <= 0:
			frappe.throw(_("Target Inspection Take Spacing must be greater than zero."))

	def validate_no_active_contract(self):
		existing = frappe.db.get_value(
			"Outgrower Production Contract",
			{
				"farm_plot": self.farm_plot,
				"docstatus": 1,
				"name": ["!=", self.name],
				"status": ["in", ["Active", "Suspended"]],
			},
		)
		if existing:
			frappe.throw(
				_("Farm Plot {0} already has active Production Contract {1}.").format(
					frappe.bold(self.farm_plot),
					frappe.bold(existing),
				)
			)


def is_planting_window_within_season(
	season_start_date,
	season_end_date,
	planting_start_date,
	planting_end_date,
):
	return (
		getdate(season_start_date)
		<= getdate(planting_start_date)
		<= getdate(planting_end_date)
		<= getdate(season_end_date)
	)


@frappe.whitelist()
def ensure_supplier(outgrower):
	require_outgrower_manager()
	return ensure_outgrower_supplier(outgrower)


@frappe.whitelist()
def create_crop_cycle(production_contract):
	require_outgrower_manager()
	contract = frappe.get_doc("Outgrower Production Contract", production_contract)
	if contract.docstatus != 1 or contract.status != "Active":
		frappe.throw(_("Submit and activate the Production Contract before creating a Crop Cycle."))
	if contract.linked_crop_cycle and frappe.db.exists("Crop Cycle", contract.linked_crop_cycle):
		return contract.linked_crop_cycle
	existing = frappe.db.get_value("Crop Cycle", {"plot": contract.farm_plot}, "name")
	if existing:
		frappe.throw(
			_("Farm Plot {0} already has Crop Cycle {1}.").format(
				frappe.bold(contract.farm_plot),
				frappe.bold(existing),
			)
		)

	cycle = frappe.get_doc(
		{
			"doctype": "Crop Cycle",
			"crop_cycle_id": f"CC-{contract.name}",
			"production_contract": contract.name,
			"start_date": contract.planting_start_date,
		}
	).insert(ignore_permissions=True)
	contract.db_set("linked_crop_cycle", cycle.name, update_modified=False)
	return cycle.name


@frappe.whitelist()
def create_erpnext_contract(production_contract):
	require_outgrower_manager()
	contract = frappe.get_doc("Outgrower Production Contract", production_contract)
	if contract.docstatus != 1:
		frappe.throw(_("Submit the Production Contract before creating its Supplier Contract."))
	if contract.erpnext_contract and frappe.db.exists("Contract", contract.erpnext_contract):
		return contract.erpnext_contract

	terms = (
		f"<p><strong>Production Contract:</strong> {frappe.utils.escape_html(contract.name)}</p>"
		f"<p><strong>Crop:</strong> {frappe.utils.escape_html(contract.crop)}; "
		f"<strong>Variety:</strong> {frappe.utils.escape_html(contract.variety)}; "
		f"<strong>Category:</strong> {frappe.utils.escape_html(contract.production_category)}</p>"
		f"<p><strong>Input and advance recovery:</strong> {contract.input_recovery_terms}</p>"
		f"{contract.quality_standard_terms or ''}"
		f"{contract.farmer_obligations or ''}"
		f"{contract.supervisor_obligations or ''}"
		f"{contract.termination_terms or ''}"
	)
	erp_contract = frappe.get_doc(
		{
			"doctype": "Contract",
			"party_type": "Supplier",
			"party_name": contract.supplier,
			"start_date": contract.contract_start_date,
			"end_date": contract.contract_end_date,
			"is_signed": 1,
			"contract_terms": terms,
		}
	).insert(ignore_permissions=True)
	contract.db_set("erpnext_contract", erp_contract.name, update_modified=False)
	return erp_contract.name
