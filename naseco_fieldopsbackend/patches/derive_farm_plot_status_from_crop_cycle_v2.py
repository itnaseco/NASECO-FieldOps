import frappe


def execute():
	"""Reserve plots assigned to any unfinished Crop Cycle."""
	occupied_plots = set(
		frappe.get_all(
			"Crop Cycle",
			filters={
				"status": ["!=", "COMPLETED"],
				"plot": ["is", "set"],
			},
			pluck="plot",
		)
	)

	for plot_name in frappe.get_all("Farm Plot", pluck="name"):
		frappe.db.set_value(
			"Farm Plot",
			plot_name,
			"status",
			"Active" if plot_name in occupied_plots else "Idle",
			update_modified=False,
		)
