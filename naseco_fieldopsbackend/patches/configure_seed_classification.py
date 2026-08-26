import frappe


SEED_CATEGORIES = (
    ("Pre-Basic", "PRE-BASIC", 10),
    ("Basic", "BASIC", 20),
    ("Certified", "CERTIFIED", 30),
)
SEED_CLASSES = (
    ("G1", "Generation 1", 1, 10),
    ("G2", "Generation 2", 2, 20),
    ("G3", "Generation 3", 3, 30),
    ("C1", "Certified 1", 1, 40),
    ("C2", "Certified 2", 2, 50),
)


def execute():
    for name, code, sequence in SEED_CATEGORIES:
        if not frappe.db.exists("Seed Category", name):
            frappe.get_doc({
                "doctype": "Seed Category",
                "category_name": name,
                "category_code": code,
                "sequence": sequence,
                "enabled": 1,
            }).insert(ignore_permissions=True)

    for code, name, generation, sequence in SEED_CLASSES:
        if not frappe.db.exists("Seed Class", code):
            frappe.get_doc({
                "doctype": "Seed Class",
                "class_code": code,
                "class_name": name,
                "generation_number": generation,
                "sequence": sequence,
                "enabled": 1,
            }).insert(ignore_permissions=True)

    frappe.clear_cache()
