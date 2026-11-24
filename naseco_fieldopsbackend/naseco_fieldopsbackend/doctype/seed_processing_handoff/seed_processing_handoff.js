frappe.ui.form.on("Seed Processing Handoff", {
	async refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("New Finished Batch"), () => {
			frappe.new_doc("Seed Finished Batch", {processing_handoff: frm.doc.name});
		}, __("Create"));
		frm.add_custom_button(__("View Finished Batches"), () => {
			frappe.set_route("List", "Seed Finished Batch", {processing_handoff: frm.doc.name});
		}, __("Navigate"));
		const response = await frm.call("get_reconciliation");
		const totals = response.message;
		if (!totals) return;
		const format = (value) => frappe.format(value, {fieldtype: "Float", precision: 1});
		frm.fields_dict.reconciliation_html.$wrapper.html(`
			<div class="row form-section">
				<div class="col-sm-3">Dispatched: ${format(totals.dispatched_qty_kg)} kg</div>
				<div class="col-sm-3">Finished: ${format(totals.received_qty_kg)} kg</div>
				<div class="col-sm-3">Batches: ${totals.batch_count}</div>
				<div class="col-sm-3">Difference: ${format(totals.difference_qty_kg)} kg</div>
			</div>
		`);
	}
});
