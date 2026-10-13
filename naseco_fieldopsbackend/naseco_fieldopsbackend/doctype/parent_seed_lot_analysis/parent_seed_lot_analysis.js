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
