frappe.ui.form.on("Outgrower Pricing Policy", {
	setup(frm) {
		frm.set_query("season", () => ({
			filters: { start_date: ["<=", frm.doc.effective_to || frappe.datetime.get_today()] }
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.dashboard.add_indicator(__("Approved pricing policy"), "green");
		}
	}
});

// Seed classification master filters.
frappe.ui.form.on("Outgrower Pricing Policy", {
	setup(frm) {
		frm.set_query("production_category", () => ({ filters: { enabled: 1 } }));
		frm.set_query("seed_class", () => ({ filters: { enabled: 1 } }));
	}
});
