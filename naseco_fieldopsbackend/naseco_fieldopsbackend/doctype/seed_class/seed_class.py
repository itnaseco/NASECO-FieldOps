import frappe
from frappe import _
from frappe.model.document import Document


class SeedClass(Document):
    def validate(self):
        if self.generation_number is not None and self.generation_number < 0:
            frappe.throw(_("Generation Number cannot be negative."))
