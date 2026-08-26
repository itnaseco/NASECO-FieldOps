import frappe
from frappe import _
from frappe.model.document import Document


class CropVariety(Document):
    def validate(self):
        self.validate_seed_items()

    def validate_seed_items(self):
        seen = set()
        defaults = set()
        for row in self.seed_items or []:
            key = (row.seed_category, row.seed_class, row.item_purpose)
            if key in seen:
                frappe.throw(
                    _("Seed item mapping row {0} duplicates Category, Class and Purpose.").format(row.idx)
                )
            seen.add(key)

            seed_class = frappe.db.get_value(
                "Seed Class", row.seed_class, ["enabled"], as_dict=True
            )
            if not seed_class or not seed_class.enabled:
                frappe.throw(_("Seed Class in row {0} must be enabled.").format(row.idx))
            if not frappe.db.get_value("Seed Category", row.seed_category, "enabled"):
                frappe.throw(_("Seed Category in row {0} must be enabled.").format(row.idx))

            item = frappe.db.get_value(
                "Item", row.item_code, ["disabled", "is_stock_item"], as_dict=True
            )
            if not item or item.disabled or not item.is_stock_item:
                frappe.throw(_("Item in row {0} must be an enabled stock Item.").format(row.idx))
            if row.item_purpose == "Parent Seed" and not self.can_be_used_as_parent_seed:
                frappe.throw(
                    _("Enable Can Be Used as Parent Seed before adding parent-seed Items.")
                )
            if row.is_default:
                default_key = (row.seed_category, row.item_purpose)
                if default_key in defaults:
                    frappe.throw(
                        _("Only one default Item is allowed per Seed Category and Purpose.")
                    )
                defaults.add(default_key)


@frappe.whitelist()
def create_seed_item(variety, item_code, item_name, item_group, stock_uom,
                     seed_category, seed_class, item_purpose, is_default=0):
    variety_doc = frappe.get_doc("Crop Variety", variety)
    variety_doc.check_permission("write")
    if not frappe.has_permission("Item", "create"):
        frappe.throw(_("You need Create permission on Item to create a seed Item."), frappe.PermissionError)
    if item_purpose not in ("Parent Seed", "Raw Seed", "Finished Seed"):
        frappe.throw(_("Invalid seed Item purpose."))
    if item_purpose == "Parent Seed" and not variety_doc.can_be_used_as_parent_seed:
        frappe.throw(_("Enable Can Be Used as Parent Seed before creating a parent-seed Item."))

    from naseco_fieldopsbackend.seed_configuration import validate_seed_scope
    validate_seed_scope(seed_category, seed_class)
    if frappe.db.exists("Item", item_code):
        frappe.throw(_("Item {0} already exists.").format(frappe.bold(item_code)))

    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_name,
        "item_group": item_group,
        "stock_uom": stock_uom,
        "is_stock_item": 1,
        "has_batch_no": 1,
    }).insert()
    variety_doc.append("seed_items", {
        "seed_category": seed_category,
        "seed_class": seed_class,
        "item_purpose": item_purpose,
        "item_code": item.name,
        "is_default": is_default,
    })
    variety_doc.save()
    return item.name
