// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.ui.form.on("Season", {
	refresh(frm) {
		if (frm.is_new()) return;

		frappe.db.get_value("Season Production Plan", {
			season: frm.doc.name,
			docstatus: ["<", 2]
		}, "name").then(({ message }) => {
			if (message?.name) {
				frm.add_custom_button(__("Open Production Plan"), () => {
					frappe.set_route("Form", "Season Production Plan", message.name);
				}, __("Navigate"));
				frm.add_custom_button(__("Open Command Centre"), () => {
					frappe.set_route("season-command-centre", { plan: message.name });
				}, __("Navigate"));
			} else if (frappe.user.has_role("Outgrower Manager")) {
				frm.add_custom_button(__("Create Production Plan"), () => {
					frappe.new_doc("Season Production Plan", {
						season: frm.doc.name,
						plan_title: `${frm.doc.season_name} Production Plan`
					});
				}, __("Create"));
			}
		});
	}
});
