import frappe

from naseco_fieldopsbackend.patches.upgrade_flexible_quality_templates import (
	_backfill_parameter_rows,
)


def execute():
	"""Run after schema synchronization so template-owned rows persist."""
	frappe.clear_cache(doctype="Inspection Template")
	frappe.clear_cache(doctype="Inspection Template Parameter")
	frappe.db.sql(
		"""
		update `tabInspection Template`
		set lifecycle_status = case
				when active = 1 and ifnull(lifecycle_status, '') = '' then 'Published'
				else lifecycle_status
			end,
			configuration_version = coalesce(nullif(configuration_version, 0), 1)
		"""
	)
	_backfill_parameter_rows()

