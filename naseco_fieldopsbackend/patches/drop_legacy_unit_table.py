# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

from naseco_fieldopsbackend.patches.migrate_unit_to_uom import drop_legacy_unit_table


def execute():
	"""Drop the orphan custom Unit table after its data has moved to UOM."""
	drop_legacy_unit_table()
