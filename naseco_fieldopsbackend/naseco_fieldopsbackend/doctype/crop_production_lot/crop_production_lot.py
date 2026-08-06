import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, date_diff, flt

from naseco_fieldopsbackend.fieldops_finance import create_todo


class CropProductionLot(Document):
	def before_validate(self):
		self.populate_context()
		self.set_collection_due_date()
		if self.planting_start_date and self.status == "Planned":
			self.status = "Planted"
		if self.crib_ready_date and self.status not in ("Delivered", "Rejected", "Closed"):
			self.status = "Harvest Ready"

	def validate(self):
		self.validate_planting_period()
		self.validate_unique_lot_number()
		self.validate_area()
		self.validate_parent_seed_batch()

	def on_update(self):
		self.create_collection_todo()

	def populate_context(self):
		if not self.crop_cycle:
			return
		cycle = frappe.db.get_value(
			"Crop Cycle",
			self.crop_cycle,
			["production_contract", "plot", "crop", "variety", "season"],
			as_dict=True,
		)
		if not cycle:
			frappe.throw(_("Crop Cycle {0} does not exist.").format(self.crop_cycle))
		self.production_contract = cycle.production_contract
		self.plot = cycle.plot
		self.crop = cycle.crop
		self.variety = cycle.variety
		self.season = cycle.season
		self.outgrower = frappe.db.get_value("Farm Plot", cycle.plot, "outgrower")
		self.assigned_supervisor = frappe.db.get_value(
			"Outgrower", self.outgrower, "assigned_supervisor"
		)
		contract = frappe.db.get_value(
			"Outgrower Production Contract",
			cycle.production_contract,
			["parent_seed_item"],
			as_dict=True,
		)
		if contract:
			self.parent_seed_item = self.parent_seed_item or contract.parent_seed_item

	def validate_planting_period(self):
		if not self.planting_start_date or not self.planting_end_date:
			return
		days = date_diff(self.planting_end_date, self.planting_start_date)
		if days < 0:
			frappe.throw(_("Planting Completed cannot be before Planting Started."))
		if days > 4:
			frappe.throw(
				_("A production lot may cover at most five consecutive planting days.")
			)

	def validate_unique_lot_number(self):
		existing = frappe.db.get_value(
			"Crop Production Lot",
			{
				"crop_cycle": self.crop_cycle,
				"lot_number": self.lot_number,
				"name": ["!=", self.name or ""],
			},
		)
		if existing:
			frappe.throw(
				_("Lot Number {0} already exists for this Crop Cycle.").format(self.lot_number)
			)

	def validate_area(self):
		if flt(self.area_hectares) <= 0:
			frappe.throw(_("Lot Area must be greater than zero."))
		other_area = sum(
			flt(row.area_hectares)
			for row in frappe.get_all(
				"Crop Production Lot",
				filters={
					"crop_cycle": self.crop_cycle,
					"name": ["!=", self.name or ""],
					"status": ["!=", "Rejected"],
				},
				fields=["area_hectares"],
			)
		)
		contracted_area = flt(
			frappe.db.get_value(
				"Outgrower Production Contract",
				self.production_contract,
				"contracted_area_hectares",
			)
		)
		if contracted_area and other_area + flt(self.area_hectares) > contracted_area:
			frappe.throw(
				_("Total production-lot area cannot exceed the contracted area of {0} hectares.").format(
					contracted_area
				)
			)
		if flt(self.accepted_area_hectares) + flt(self.rejected_area_hectares) > flt(self.area_hectares):
			frappe.throw(_("Accepted and Rejected Area cannot exceed the Lot Area."))

	def validate_parent_seed_batch(self):
		if not self.parent_seed_batch or not self.parent_seed_item:
			return
		batch_item = frappe.db.get_value("Batch", self.parent_seed_batch, "item")
		if batch_item and batch_item != self.parent_seed_item:
			frappe.throw(_("Parent Seed Batch must belong to the selected Parent Seed Item."))

	def set_collection_due_date(self):
		if not self.crib_ready_date:
			self.collection_due_date = None
			return
		policy = frappe.db.get_value(
			"Outgrower Production Contract", self.production_contract, "pricing_policy"
		)
		days = (
			frappe.db.get_value("Outgrower Pricing Policy", policy, "collection_due_days")
			if policy
			else 30
		)
		self.collection_due_date = add_days(self.crib_ready_date, days or 30)

	def create_collection_todo(self):
		if not self.crib_ready_date or not self.collection_due_date:
			return
		allocated_to = frappe.db.get_value(
			"Outgrower Production Contract", self.production_contract, "company_signatory"
		)
		create_todo(
			allocated_to,
			"Crop Production Lot",
			self.name,
			f"Arrange harvest collection for {self.name}",
			self.collection_due_date,
			"High",
		)
