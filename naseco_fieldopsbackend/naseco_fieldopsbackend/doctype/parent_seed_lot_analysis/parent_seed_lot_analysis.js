// Copyright (c) 2026, NASECO and contributors
// For license information, please see license.txt

frappe.ui.form.on("Parent Seed Lot Analysis", {
	setup(frm) {
		frm.set_query("item_code", () => ({
			query: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.parent_seed_item_query",
			filters: {
				parent_variety: frm.doc.parent_variety,
				seed_category: frm.doc.seed_category,
				seed_class: frm.doc.seed_class
			}
		}));
		frm.set_query("batch_no", () => ({filters: {item: frm.doc.item_code, disabled: 0}}));
		frm.set_query("finished_batch", () => ({filters: frm.doc.item_code ? {item_code: frm.doc.item_code} : {}}));
	},
	async finished_batch(frm) {
		if (!frm.doc.finished_batch) return;
		const result = await frappe.db.get_value("Seed Finished Batch", frm.doc.finished_batch,
			["item_code", "batch_no", "harvest_lot"]);
		if (!result.message) return;
		const source = await frappe.db.get_value("Seed Field Harvest Lot", result.message.harvest_lot,
			["variety", "season"]);
		await frm.set_value("parent_variety", source.message?.variety || frm.doc.parent_variety);
		await frm.set_value("season", source.message?.season || frm.doc.season);
		await frm.set_value("item_code", result.message.item_code);
		await frm.set_value("batch_no", result.message.batch_no);
	},
	parent_variety(frm) {
		frm.set_value("item_code", null);
		frm.set_value("batch_no", null);
	},
	seed_category(frm) {
		frm.set_value("item_code", null);
		frm.set_value("batch_no", null);
	},
	seed_class(frm) {
		frm.set_value("item_code", null);
		frm.set_value("batch_no", null);
	},
	item_code(frm) {
		frm.set_value("batch_no", null);
	}
});
