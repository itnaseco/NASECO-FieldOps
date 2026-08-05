frappe.ui.form.on("Production Contract Template", {
	setup(frm) {
		frm.set_query("pricing_policy", () => ({
			filters: {
				docstatus: 1,
				status: "Active",
				season: frm.doc.season,
				crop: frm.doc.crop,
				production_category: frm.doc.production_category
			}
		}));
	}
});
