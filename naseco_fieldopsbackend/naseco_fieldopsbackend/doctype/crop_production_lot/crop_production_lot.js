frappe.ui.form.on("Crop Production Lot", {
	setup(frm) {
		frm.set_query("parent_seed_batch", () => ({
			filters: { item: frm.doc.parent_seed_item, disabled: 0 }
		}));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Open Crop Cycle"), () => {
			frappe.set_route("Form", "Crop Cycle", frm.doc.crop_cycle);
		}, __("Navigate"));
		frm.add_custom_button(__("New Harvest Quality Assessment"), () => {
			frappe.new_doc("Seed Harvest Quality Assessment", {
				production_lot: frm.doc.name,
				crop_cycle: frm.doc.crop_cycle,
				production_contract: frm.doc.production_contract,
				batch_no: frm.doc.harvest_batch
			});
		}, __("Create"));
		frm.add_custom_button(__("View Quality Assessments"), () => {
			frappe.set_route("List", "Seed Harvest Quality Assessment", {
				production_lot: frm.doc.name
			});
		}, __("Navigate"));
	}
});
