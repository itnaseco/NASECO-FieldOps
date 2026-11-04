frappe.listview_settings["Outgrower Production Contract"] = {
	onload(listview) {
		frappe.require("/assets/naseco_fieldopsbackend/js/season_list_defaults.js", () => {
			naseco_fieldops.setup_season_list_defaults(listview);
		});
	}
};
