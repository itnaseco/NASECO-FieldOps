frappe.ui.form.on("Production Contract Template", {
	setup(frm) {
		frm.set_query("pricing_policy", () => ({
			filters: {
				docstatus: 1,
				status: "Active",
				season: frm.doc.season,
				crop: frm.doc.crop,
				production_category: frm.doc.production_category,
				seed_class: frm.doc.seed_class
			}
		}));
	}
});

// Seed classification master filters.
frappe.ui.form.on("Production Contract Template", {
	setup(frm) {
		frm.set_query("production_category", () => ({ filters: { enabled: 1 } }));
		frm.set_query("seed_class", () => ({ filters: { enabled: 1 } }));
	}
});
