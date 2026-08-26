# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe

from naseco_fieldopsbackend.patches.configure_fieldops_operating_model import (
	ensure_custom_permissions,
)


def execute():
	ensure_custom_permissions()
	frappe.clear_cache(doctype="Crop Recipe")
