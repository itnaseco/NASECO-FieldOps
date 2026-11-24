frappe.ui.form.on("Seed Field Harvest Lot", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("New Processing Handoff"), () => {
			frappe.new_doc("Seed Processing Handoff", {harvest_lot: frm.doc.name});
		}, __("Create"));
		frm.add_custom_button(__("View Processing Handoffs"), () => {
			frappe.set_route("List", "Seed Processing Handoff", {harvest_lot: frm.doc.name});
		}, __("Navigate"));
	}
});
