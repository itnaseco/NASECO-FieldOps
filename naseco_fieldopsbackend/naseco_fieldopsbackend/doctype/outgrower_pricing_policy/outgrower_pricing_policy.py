import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from naseco_fieldopsbackend.roles import OUTGROWER_MANAGER_ROLE


class OutgrowerPricingPolicy(Document):
	def validate(self):
		self.validate_dates()
		self.validate_thresholds()
		self.validate_bands()

	def before_submit(self):
		require_policy_approver()
		self.validate_single_active_policy()
		self.status = "Active"
		self.approved_by = frappe.session.user

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def validate_dates(self):
		if self.effective_from and self.effective_to and getdate(self.effective_from) > getdate(self.effective_to):
			frappe.throw(_("Effective From cannot be after Effective To."))

	def validate_thresholds(self):
		for fieldname in (
			"moisture_target_percent",
			"minimum_germination_percent",
			"undersize_threshold_percent",
			"screen_weight_deduction_percent",
			"reject_threshold_percent",
			"reject_value_deduction_percent",
			"high_bonus_purity_threshold",
			"standard_bonus_purity_threshold",
			"late_interest_percent_per_month",
			"blacklist_purity_threshold",
		):
			if not 0 <= flt(self.get(fieldname)) <= 100:
				frappe.throw(_("{0} must be between zero and 100.").format(self.meta.get_label(fieldname)))
		if flt(self.minimum_seed_yield_kg_per_acre) > flt(self.quota_kg_per_acre):
			frappe.throw(_("Minimum Seed Yield cannot exceed the Contract Quota."))

	def validate_bands(self):
		if not self.pricing_bands:
			frappe.throw(_("At least one pricing band is required."))
		for row in self.pricing_bands:
			if flt(row.maximum_yield_kg_per_acre) and flt(row.maximum_yield_kg_per_acre) <= flt(
				row.minimum_yield_kg_per_acre
			):
				frappe.throw(_("Maximum Yield must exceed Minimum Yield in row {0}.").format(row.idx))
			if flt(row.maximum_purity_percent) and flt(row.maximum_purity_percent) <= flt(
				row.minimum_purity_percent
			):
				frappe.throw(_("Maximum Purity must exceed Minimum Purity in row {0}.").format(row.idx))
			if row.price_basis == "Fixed Rate" and flt(row.rate_per_kg) <= 0:
				frappe.throw(_("A positive fixed rate is required in pricing row {0}.").format(row.idx))

	def validate_single_active_policy(self):
		existing = frappe.db.get_value(
			"Outgrower Pricing Policy",
			{
				"season": self.season,
				"crop": self.crop,
				"production_category": self.production_category,
				"docstatus": 1,
				"status": "Active",
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("Active pricing policy {0} already covers this Season, Crop and Seed Category.").format(
					frappe.bold(existing)
				)
			)


def require_policy_approver():
	if frappe.session.user == "Administrator":
		return
	if not {OUTGROWER_MANAGER_ROLE, "System Manager"}.intersection(frappe.get_roles()):
		frappe.throw(
			_("Only an Outgrower Manager or System Manager can approve a pricing policy."),
			frappe.PermissionError,
		)


def find_pricing_band(policy, yield_kg_per_acre, genetic_purity_percent):
	yield_value = flt(yield_kg_per_acre)
	purity_value = flt(genetic_purity_percent)
	for row in policy.pricing_bands:
		yield_matches = yield_value >= flt(row.minimum_yield_kg_per_acre) and (
			not flt(row.maximum_yield_kg_per_acre)
			or yield_value < flt(row.maximum_yield_kg_per_acre)
		)
		purity_matches = purity_value >= flt(row.minimum_purity_percent) and (
			not flt(row.maximum_purity_percent)
			or purity_value < flt(row.maximum_purity_percent)
		)
		if yield_matches and purity_matches:
			return row
	return None


def calculate_harvest_pricing(
	policy,
	net_dry_qty,
	eligible_area_acres,
	genetic_purity_percent,
	germination_percent,
	undersize_percent=0,
	reject_percent=0,
	grain_rate=None,
	force_rejected=False,
):
	"""Calculate an auditable pricing result without creating accounting entries."""
	qty = max(flt(net_dry_qty), 0)
	area = flt(eligible_area_acres)
	if area <= 0:
		frappe.throw(_("Eligible acreage must be greater than zero for harvest pricing."))

	yield_per_acre = qty / area
	band = find_pricing_band(policy, yield_per_acre, genetic_purity_percent)
	grain_rate = flt(grain_rate or policy.grain_rate_per_kg)
	force_grain = flt(germination_percent) < flt(policy.minimum_germination_percent)
	price_basis = "Rejected" if force_rejected else ("Grain Price" if force_grain else None)
	if not price_basis:
		price_basis = band.price_basis if band else "Grain Price"

	quota_qty = area * flt(policy.quota_kg_per_acre)
	base_qty = excess_qty = grain_qty = 0
	base_rate = excess_rate = 0
	if price_basis == "Rejected":
		gross_value = 0
	elif price_basis == "Grain Price":
		if grain_rate <= 0:
			frappe.throw(_("A positive Grain Rate is required for grain-price settlement."))
		grain_qty = qty
		base_rate = grain_rate
		gross_value = grain_qty * grain_rate
	else:
		base_qty = min(qty, quota_qty)
		excess_qty = max(qty - quota_qty, 0)
		base_rate = flt(band.rate_per_kg)
		excess_rate = flt(policy.excess_rate_per_kg)
		gross_value = base_qty * base_rate + excess_qty * excess_rate

	screen_deduction = (
		gross_value * flt(policy.screen_weight_deduction_percent) / 100
		if flt(undersize_percent) > flt(policy.undersize_threshold_percent)
		else 0
	)
	reject_deduction = (
		gross_value * flt(policy.reject_value_deduction_percent) / 100
		if flt(reject_percent) > flt(policy.reject_threshold_percent)
		else 0
	)
	initial_payable = max(gross_value - screen_deduction - reject_deduction, 0)

	bonus_rate = 0
	if price_basis == "Fixed Rate":
		if flt(genetic_purity_percent) > flt(policy.high_bonus_purity_threshold):
			bonus_rate = flt(policy.high_bonus_rate_per_kg)
		elif flt(genetic_purity_percent) > flt(policy.standard_bonus_purity_threshold):
			bonus_rate = flt(policy.standard_bonus_rate_per_kg)

	return frappe._dict(
		pricing_band=band.band_name if band else None,
		price_basis=price_basis,
		net_dry_qty=qty,
		eligible_area_acres=area,
		yield_kg_per_acre=yield_per_acre,
		base_quota_qty=base_qty,
		excess_qty=excess_qty,
		grain_qty=grain_qty,
		base_rate=base_rate,
		excess_rate=excess_rate,
		gross_value=gross_value,
		screen_deduction=screen_deduction,
		reject_deduction=reject_deduction,
		total_quality_deduction=screen_deduction + reject_deduction,
		initial_payable_value=initial_payable,
		potential_bonus_rate=bonus_rate,
		potential_bonus_amount=qty * bonus_rate,
	)
