import re

import frappe
from frappe import _
from frappe.model.document import Document


class StageDefinition(Document):
    def validate(self):
        self.stage_code = (self.stage_code or "").strip().upper()
        self.stage_name = (self.stage_name or "").strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.stage_code):
            frappe.throw(_("Stage Code must use uppercase letters, digits and underscores, starting with a letter."))
        if not self.stage_name:
            frappe.throw(_("Stage Name is required."))
        previous = self.get_doc_before_save()
        if previous and previous.stage_code != self.stage_code:
            frappe.throw(_("Stage Code cannot change after creation; retire this definition and create a new one."))
        if previous and previous.stage_name != self.stage_name and frappe.db.exists(
            "Recipe Stage", {"stage_definition": self.name}
        ):
            frappe.throw(_("Stage Name cannot change while recipes reference this definition."))
