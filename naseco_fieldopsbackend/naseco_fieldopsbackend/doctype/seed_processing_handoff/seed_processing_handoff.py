import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class SeedProcessingHandoff(Document):
	"""Records a transfer to processing without posting manufacturing or stock."""

	@frappe.whitelist()
	def get_reconciliation(self):
		if self.is_new() or not isinstance(self.name, str) or not self.name:
			frappe.throw(_("Save the Processing Handoff before viewing reconciliation."))
		self.check_permission("read")
		rows = frappe.db.get_all(
			"Seed Finished Batch",
			filters={"processing_handoff": self.name},
			fields=["sum(received_qty_kg) as total", "count(name) as batch_count"],
		)
		received = flt(rows[0].total) if rows else 0
		return {
			"dispatched_qty_kg": flt(self.dispatched_qty_kg),
			"received_qty_kg": received,
			"batch_count": rows[0].batch_count if rows else 0,
			"difference_qty_kg": flt(self.dispatched_qty_kg) - received,
		}

	def validate(self):
		if not self.is_new():
			previous = self.get_doc_before_save()
			if previous and previous.harvest_lot != self.harvest_lot:
				frappe.throw(_("Harvest Lot cannot change after the handoff is saved."))
			if previous and flt(previous.dispatched_qty_kg) != flt(self.dispatched_qty_kg):
				if frappe.db.exists("Seed Finished Batch", {"processing_handoff": self.name}):
					frappe.throw(_("Dispatched Quantity cannot change after finished Batches are linked."))
		if flt(self.dispatched_qty_kg) <= 0:
			frappe.throw(_("Dispatched Quantity (kg) must be greater than zero."))
		if self.harvest_lot:
			lot = frappe.db.get_value(
				"Seed Field Harvest Lot", self.harvest_lot,
				["harvest_date", "accepted_qty_kg", "harvested_qty_kg"], as_dict=True,
				for_update=True,
			)
			if not lot:
				frappe.throw(_("Seed Field Harvest Lot {0} does not exist.").format(self.harvest_lot))
			if getdate(self.dispatch_date) < getdate(lot.harvest_date):
				frappe.throw(_("Dispatch Date cannot be before Harvest Date."))
			other = frappe.db.get_all(
				"Seed Processing Handoff",
				filters={"harvest_lot": self.harvest_lot, "name": ["!=", self.name or ""]},
				fields=["sum(dispatched_qty_kg) as total"],
			)
			dispatched = flt(other[0].total) if other else 0
			available = flt(lot.accepted_qty_kg)
			if available <= 0:
				frappe.throw(_("Record an accepted harvest quantity before dispatching this lot."))
			if dispatched + flt(self.dispatched_qty_kg) > available:
				frappe.throw(_("Total dispatched quantity exceeds the harvest lot quantity of {0} kg.").format(available))
		if self.processing_system == "External" and not self.processor_name:
			frappe.throw(_("Processor Name is required for an external handoff."))

	def on_trash(self):
		if frappe.db.exists("Seed Finished Batch", {"processing_handoff": self.name}):
			frappe.throw(_("Remove linked finished Batch records before deleting this handoff."))
