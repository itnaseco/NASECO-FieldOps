import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HarvestRejectDisposition(Document):
    def before_validate(self):
        self.populate_context()

    def validate(self):
        if flt(self.rejected_qty) <= 0:
            frappe.throw(_("Rejected Quantity must be greater than zero."))
        if not self.source_warehouse:
            frappe.throw(_("Source Warehouse is required."))
        if self.disposition != "Destroy" and not self.target_warehouse:
            frappe.throw(_("Target Warehouse is required for this disposition."))
        if self.target_warehouse and self.target_warehouse == self.source_warehouse:
            frappe.throw(_("Source and Target Warehouses must be different."))
        assessed = flt(frappe.db.get_value("Seed Harvest Quality Assessment", self.quality_assessment, "net_dry_qty"))
        already = sum(flt(row.rejected_qty) for row in frappe.get_all(
            self.doctype,
            filters={"quality_assessment": self.quality_assessment, "docstatus": 1, "name": ["!=", self.name]},
            fields=["rejected_qty"],
        ))
        if assessed and already + flt(self.rejected_qty) > assessed:
            frappe.throw(_("Cumulative reject dispositions cannot exceed the assessed net dry quantity."))

    def before_submit(self):
        if not self.approved_by:
            self.approved_by = frappe.session.user

    def on_submit(self):
        self.create_stock_movement()

    def before_cancel(self):
        if self.stock_entry and frappe.db.get_value("Stock Entry", self.stock_entry, "docstatus") == 1:
            frappe.throw(_("Cancel Stock Entry {0} before cancelling this disposition.").format(self.stock_entry))

    def on_cancel(self):
        if self.stock_entry and frappe.db.get_value("Stock Entry", self.stock_entry, "docstatus") == 0:
            frappe.delete_doc("Stock Entry", self.stock_entry, ignore_permissions=True)
        self.db_set("status", "Cancelled", update_modified=False)

    def populate_context(self):
        if not self.quality_assessment:
            return
        assessment = frappe.db.get_value(
            "Seed Harvest Quality Assessment",
            self.quality_assessment,
            ["crop_cycle", "production_contract", "production_lot", "purchase_receipt", "purchase_receipt_item", "item_code", "batch_no", "uom", "docstatus"],
            as_dict=True,
        )
        if not assessment or assessment.docstatus != 1:
            frappe.throw(_("A submitted Seed Harvest Quality Assessment is required."))
        for fieldname in ("crop_cycle", "production_contract", "production_lot", "purchase_receipt", "purchase_receipt_item", "item_code", "batch_no", "uom"):
            self.set(fieldname, assessment.get(fieldname))
        settings = frappe.get_single("FieldOps Settings")
        self.source_warehouse = self.source_warehouse or settings.harvest_quarantine_warehouse or settings.harvest_warehouse
        if not self.target_warehouse:
            self.target_warehouse = settings.grain_warehouse if self.disposition == "Downgrade to Grain" else settings.reject_warehouse

    def create_stock_movement(self):
        if self.stock_entry:
            return self.stock_entry
        company = frappe.db.get_value("Outgrower Production Contract", self.production_contract, "company")
        purpose = "Material Issue" if self.disposition == "Destroy" else "Material Transfer"
        row = {
            "item_code": self.item_code,
            "qty": self.rejected_qty,
            "uom": self.uom,
            "s_warehouse": self.source_warehouse,
            "t_warehouse": None if purpose == "Material Issue" else self.target_warehouse,
            "batch_no": self.batch_no,
        }
        entry = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": purpose,
            "custom_harvest_reject_disposition": self.name,
            "purpose": purpose,
            "company": company,
            "custom_production_contract": self.production_contract,
            "crop_cycle": self.crop_cycle,
            "remarks": f"Harvest reject disposition {self.name}: {self.disposition}",
            "items": [row],
        })
        entry.insert(ignore_permissions=True)
        self.db_set({"stock_entry": entry.name, "status": "Stock Entry Draft"}, update_modified=False)
        return entry.name


@frappe.whitelist()
def create_stock_entry(disposition):
    doc = frappe.get_doc("Harvest Reject Disposition", disposition)
    if doc.docstatus != 1:
        frappe.throw(_("Submit the disposition before creating its Stock Entry."))
    return doc.create_stock_movement()
