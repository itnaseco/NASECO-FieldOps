
// Seed classification master filters.
frappe.ui.form.on("Inspection Standard", {
	setup(frm) {
		frm.set_query("production_category", () => ({ filters: { enabled: 1 } }));
		frm.set_query("seed_class", () => ({ filters: { enabled: 1 } }));
	}
});
