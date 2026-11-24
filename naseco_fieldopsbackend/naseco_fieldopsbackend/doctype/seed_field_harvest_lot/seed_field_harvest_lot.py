import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SeedFieldHarvestLot(Document):
	"""A physical harvest lot, distinct from a planting-period production lot."""

	def before_validate(self):
		if not self.production_lot:
			return
		context = frappe.db.get_value(
			"Crop Production Lot",
			self.production_lot,
			["crop_cycle", "season", "crop", "variety"],
			as_dict=True,
		)
		if not context:
			frappe.throw(_("Crop Production Lot {0} does not exist.").format(self.production_lot))
		for field in ("crop_cycle", "season", "crop", "variety"):
			value = context.get(field)
			if self.get(field) and self.get(field) != value:
				frappe.throw(_("{0} must match the source Production Lot.").format(field))
			self.set(field, value)
		if context.crop_cycle:
			category = frappe.db.get_value("Crop Cycle", context.crop_cycle, "production_category")
			if self.production_category and self.production_category != category:
				frappe.throw(_("Production Category must match the source Crop Cycle."))
			self.production_category = category

	def validate(self):
		if not self.is_new():
			previous = self.get_doc_before_save()
			if previous and previous.production_lot != self.production_lot:
				frappe.throw(_("Production Lot cannot change after the harvest lot is saved."))
		if flt(self.harvested_qty_kg) <= 0:
			frappe.throw(_("Harvested Quantity (kg) must be greater than zero."))
		if flt(self.accepted_qty_kg) < 0 or flt(self.accepted_qty_kg) > flt(self.harvested_qty_kg):
			frappe.throw(_("Accepted Quantity (kg) must be between zero and Harvested Quantity (kg)."))
		if not self.is_new():
			frappe.db.get_value("Seed Field Harvest Lot", self.name, "name", for_update=True)
			rows = frappe.db.get_all(
				"Seed Processing Handoff", filters={"harvest_lot": self.name},
				fields=["sum(dispatched_qty_kg) as total"],
			)
			if rows and flt(rows[0].total) > flt(self.accepted_qty_kg):
				frappe.throw(_("Accepted Quantity cannot be less than quantity already dispatched."))

	def on_trash(self):
		if frappe.db.exists("Seed Processing Handoff", {"harvest_lot": self.name}):
			frappe.throw(_("Remove linked processing handoffs before deleting this harvest lot."))
