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
