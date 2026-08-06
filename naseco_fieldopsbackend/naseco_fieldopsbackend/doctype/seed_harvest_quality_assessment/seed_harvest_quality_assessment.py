import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_pricing_policy.outgrower_pricing_policy import (
	calculate_harvest_pricing,
)


QUALITY_PARAMETERS = (
	("Harvest Moisture", "moisture_percent"),
	("Seed Germination", "germination_percent"),
	("Genetic Purity", "genetic_purity_percent"),
	("Seed Vigour", "vigor_percent"),
	("Seed Below Screen Size", "undersize_percent"),
	("Harvest Rejects", "reject_percent"),
)


class SeedHarvestQualityAssessment(Document):
	def before_validate(self):
		self.populate_context()
		self.calculate_net_dry_quantity()
		self.set_disposition()
		self.calculate_provisional_pricing()

	def validate(self):
		if self.inspected_by and "Quality Inspector" not in frappe.get_roles(self.inspected_by):
			frappe.throw(
				_("{0} must have the Quality Inspector role.").format(
					frappe.bold(self.inspected_by)
				)
			)
		self.validate_percentages()
		self.validate_receipt_item()
		self.validate_quality_inspection()

	def before_submit(self):
		if not self.verified_by:
			frappe.throw(_("Verified By is required before submitting a quality assessment."))
		if not self.laboratory_certificate and not self.quality_inspection:
			frappe.throw(_("A laboratory certificate or linked Quality Inspection is required."))
		if self.quality_inspection and frappe.db.get_value(
			"Quality Inspection", self.quality_inspection, "docstatus"
		) != 1:
			frappe.throw(_("Quality Inspection must be submitted before this assessment."))
		self.assessment_status = {
			"Seed": "Seed Accepted",
			"Grain": "Accepted as Grain",
			"Rejected": "Rejected",
		}[self.disposition]

	def on_submit(self):
		self.link_receipt_item()
		self.update_production_lot()
		self.update_outgrower_eligibility()

	def on_cancel(self):
		self.db_set("assessment_status", "Cancelled", update_modified=False)
		if (
			self.purchase_receipt_item
			and frappe.db.get_value(
				"Purchase Receipt Item",
				self.purchase_receipt_item,
				"custom_seed_harvest_quality_assessment",
			)
			== self.name
		):
			frappe.db.set_value(
				"Purchase Receipt Item",
				self.purchase_receipt_item,
				"custom_seed_harvest_quality_assessment",
				None,
				update_modified=False,
			)
		self.update_production_lot()

	def populate_context(self):
		if not self.production_lot:
			return
		lot = frappe.db.get_value(
			"Crop Production Lot",
			self.production_lot,
			[
				"crop_cycle",
				"production_contract",
				"outgrower",
				"season",
				"area_hectares",
				"accepted_area_hectares",
				"harvest_batch",
			],
			as_dict=True,
		)
		if not lot:
			frappe.throw(_("Production Lot {0} does not exist.").format(self.production_lot))
		self.crop_cycle = lot.crop_cycle
		self.production_contract = lot.production_contract
		self.outgrower = lot.outgrower
		self.season = lot.season
		self.batch_no = self.batch_no or lot.harvest_batch
		self.eligible_area_hectares = lot.accepted_area_hectares or lot.area_hectares
		self.pricing_policy = frappe.db.get_value(
			"Outgrower Production Contract", lot.production_contract, "pricing_policy"
		)
		if self.pricing_policy:
			self.moisture_target_percent = frappe.db.get_value(
				"Outgrower Pricing Policy", self.pricing_policy, "moisture_target_percent"
			)
		if self.purchase_receipt_item:
			item = frappe.db.get_value(
				"Purchase Receipt Item",
				self.purchase_receipt_item,
				[
					"parent",
					"item_code",
					"stock_qty",
					"stock_uom",
					"batch_no",
				],
				as_dict=True,
			)
			if item:
				self.purchase_receipt = item.parent
				self.item_code = item.item_code
				self.gross_qty = item.stock_qty
				self.uom = item.stock_uom
				self.batch_no = self.batch_no or item.batch_no

	def calculate_net_dry_quantity(self):
		gross_qty = max(flt(self.gross_qty), 0)
		moisture = flt(self.moisture_percent)
		target = flt(self.moisture_target_percent)
		if (
			self.moisture_adjustment_method == "Normalize Down to Target"
			and moisture > target
			and target < 100
			and moisture < 100
		):
			self.net_dry_qty = gross_qty * (100 - moisture) / (100 - target)
		else:
			self.net_dry_qty = gross_qty

	def set_disposition(self):
		if not self.pricing_policy:
			self.assessment_status = "Pending Laboratory Review"
			return
		minimum_germination = flt(
			frappe.db.get_value(
				"Outgrower Pricing Policy",
				self.pricing_policy,
				"minimum_germination_percent",
			)
		)
		if self.disposition != "Rejected" and flt(self.germination_percent) < minimum_germination:
			self.disposition = "Grain"
			self.quality_decision_notes = self.quality_decision_notes or _(
				"Converted to grain because germination is below the contract minimum."
			)
		self.assessment_status = "Pending Laboratory Review"

	def calculate_provisional_pricing(self):
		if not self.pricing_policy or not flt(self.net_dry_qty) or not flt(self.eligible_area_hectares):
			return
		policy = frappe.get_doc("Outgrower Pricing Policy", self.pricing_policy)
		result = calculate_harvest_pricing(
			policy,
			self.net_dry_qty,
			self.eligible_area_hectares,
			self.genetic_purity_percent,
			self.germination_percent,
			self.undersize_percent,
			self.reject_percent,
			force_rejected=self.disposition == "Rejected",
		)
		self.provisional_yield_kg_per_hectare = result.yield_kg_per_hectare
		self.provisional_pricing_band = result.pricing_band
		self.provisional_price_basis = result.price_basis
		self.provisional_payable_value = result.initial_payable_value
		self.potential_bonus_amount = result.potential_bonus_amount
		self.bonus_status = (
			"Pending QA Approval" if result.potential_bonus_amount else "Not Eligible"
		)

	def validate_percentages(self):
		for fieldname in (
			"moisture_percent",
			"germination_percent",
			"genetic_purity_percent",
			"vigor_percent",
			"undersize_percent",
			"reject_percent",
		):
			if not 0 <= flt(self.get(fieldname)) <= 100:
				frappe.throw(_("{0} must be between zero and 100.").format(self.meta.get_label(fieldname)))

	def validate_receipt_item(self):
		if not self.purchase_receipt_item:
			return
		parent = frappe.db.get_value("Purchase Receipt Item", self.purchase_receipt_item, "parent")
		if parent != self.purchase_receipt:
			frappe.throw(_("Purchase Receipt Item does not belong to the selected Purchase Receipt."))
		if frappe.db.get_value("Purchase Receipt", self.purchase_receipt, "docstatus") != 1:
			frappe.throw(_("Purchase Receipt must be submitted before final quality assessment."))
		if self.uom != "Kg":
			frappe.throw(
				_(
					"The delivered Item must use Kg as its Stock UOM. ERPNext will "
					"convert the receipt UOM to kilograms before contract pricing."
				)
			)
		existing = frappe.db.get_value(
			"Seed Harvest Quality Assessment",
			{
				"purchase_receipt_item": self.purchase_receipt_item,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("Purchase Receipt row is already assessed by {0}.").format(
					frappe.bold(existing)
				)
			)
		item_context = frappe.db.get_value(
			"Purchase Receipt Item",
			self.purchase_receipt_item,
			["crop_cycle", "custom_production_lot"],
			as_dict=True,
		)
		if item_context.crop_cycle and item_context.crop_cycle != self.crop_cycle:
			frappe.throw(_("Purchase Receipt row belongs to a different Crop Cycle."))
		if (
			item_context.custom_production_lot
			and item_context.custom_production_lot != self.production_lot
		):
			frappe.throw(_("Purchase Receipt row belongs to a different Production Lot."))

	def validate_quality_inspection(self):
		if not self.quality_inspection:
			return
		inspection = frappe.db.get_value(
			"Quality Inspection",
			self.quality_inspection,
			["reference_type", "reference_name", "item_code", "docstatus", "status"],
			as_dict=True,
		)
		if not inspection:
			frappe.throw(_("Linked Quality Inspection does not exist."))
		if inspection.reference_type != "Purchase Receipt" or inspection.reference_name != self.purchase_receipt:
			frappe.throw(_("Quality Inspection must reference the selected Purchase Receipt."))
		if inspection.item_code != self.item_code:
			frappe.throw(_("Quality Inspection Item must match the delivered Item."))
		if self.docstatus == 1 and inspection.docstatus != 1:
			frappe.throw(_("Quality Inspection must be submitted before this assessment."))

	def update_production_lot(self):
		submitted = frappe.get_all(
			"Seed Harvest Quality Assessment",
			filters={"production_lot": self.production_lot, "docstatus": 1},
			fields=["net_dry_qty", "disposition"],
		)
		delivered_qty = sum(flt(row.net_dry_qty) for row in submitted if row.disposition != "Rejected")
		status = "Delivered" if delivered_qty else "Harvest Ready"
		if submitted and all(row.disposition == "Rejected" for row in submitted):
			status = "Rejected"
		frappe.db.set_value(
			"Crop Production Lot",
			self.production_lot,
			{"delivered_qty": delivered_qty, "status": status},
			update_modified=False,
		)

	def link_receipt_item(self):
		if not self.purchase_receipt_item:
			return
		frappe.db.set_value(
			"Purchase Receipt Item",
			self.purchase_receipt_item,
			{
				"custom_production_lot": self.production_lot,
				"custom_seed_harvest_quality_assessment": self.name,
			},
			update_modified=False,
		)

	def update_outgrower_eligibility(self):
		policy = frappe.get_doc("Outgrower Pricing Policy", self.pricing_policy)
		threshold = flt(policy.blacklist_purity_threshold)
		required = int(policy.blacklist_consecutive_seasons or 2)
		rows = frappe.get_all(
			"Seed Harvest Quality Assessment",
			filters={"outgrower": self.outgrower, "docstatus": 1},
			fields=["season", "genetic_purity_percent", "delivery_date"],
			order_by="delivery_date desc",
		)
		season_results = {}
		for row in rows:
			if row.season not in season_results:
				season_results[row.season] = flt(row.genetic_purity_percent)
			else:
				season_results[row.season] = min(
					season_results[row.season], flt(row.genetic_purity_percent)
				)
		consecutive = 0
		for purity in season_results.values():
			if purity >= threshold:
				break
			consecutive += 1
		eligibility = "Under Review" if consecutive >= required else "Eligible"
		current = frappe.db.get_value("Outgrower", self.outgrower, "eligibility_status")
		if current != "Ineligible":
			frappe.db.set_value(
				"Outgrower",
				self.outgrower,
				{
					"consecutive_low_purity_seasons": consecutive,
					"eligibility_status": eligibility,
				},
				update_modified=False,
			)


@frappe.whitelist()
def create_quality_inspection(assessment):
	doc = frappe.get_doc("Seed Harvest Quality Assessment", assessment)
	if doc.quality_inspection and frappe.db.exists("Quality Inspection", doc.quality_inspection):
		return doc.quality_inspection
	for parameter_name, _fieldname in QUALITY_PARAMETERS:
		if not frappe.db.exists("Quality Inspection Parameter", parameter_name):
			frappe.get_doc(
				{
					"doctype": "Quality Inspection Parameter",
					"parameter": parameter_name,
				}
			).insert(ignore_permissions=True)

	inspection_values = {
			"doctype": "Quality Inspection",
			"inspection_type": "Incoming",
			"reference_type": "Purchase Receipt",
			"reference_name": doc.purchase_receipt,
			"child_row_reference": doc.purchase_receipt_item,
			"item_code": doc.item_code,
			"batch_no": doc.batch_no,
			"sample_size": doc.gross_qty,
			"manual_inspection": 1,
			"inspected_by": doc.inspected_by or frappe.session.user,
			"remarks": f"Seed harvest assessment {doc.name}",
			"readings": [
				{
					"specification": label,
					"numeric": 1,
					"manual_inspection": 1,
					"reading_1": doc.get(fieldname),
				}
				for label, fieldname in QUALITY_PARAMETERS
			],
		}
	inspection_meta = frappe.get_meta("Quality Inspection")
	for fieldname, value in {
		"custom_seed_harvest_quality_assessment": doc.name,
		"custom_crop_cycle": doc.crop_cycle,
		"custom_production_lot": doc.production_lot,
		"custom_production_contract": doc.production_contract,
	}.items():
		if inspection_meta.has_field(fieldname):
			inspection_values[fieldname] = value
	quality_inspection = frappe.get_doc(inspection_values).insert(ignore_permissions=True)
	doc.db_set("quality_inspection", quality_inspection.name, update_modified=False)
	return quality_inspection.name
