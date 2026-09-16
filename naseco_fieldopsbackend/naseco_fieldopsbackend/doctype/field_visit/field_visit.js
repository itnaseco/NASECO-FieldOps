// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.ui.form.on("Field Visit", {
	refresh(frm) {
		// The Tab Break must exist in the rendered layout before it can be
		// conditionally hidden. Defining it as hidden in DocType JSON prevents
		// some Frappe versions from creating the tab DOM at all.
		frm.toggle_display("ux_visit_work_tab", false);
		frm.get_field("visit_work_summary").$wrapper.empty();
		if (frm.is_new()) return;

		const visit_name = frm.doc.name;
		frappe.call({
			method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.field_visit.field_visit.get_visit_work_summary",
			args: { visit: visit_name },
			callback: (response) => {
				if (frm.doc.name !== visit_name || frm.is_new()) return;
				const work = response.message || {};
				const groups = [
					[__("Agronomy Activities"), "Stage Activity", work.activities || []],
					[__("Agronomy Reports"), "Agronomy Report", work.reports || []],
					[__("Quality Inspections"), "Inspection", work.inspections || []],
					[__("Input Dispatches"), "Stage Input Dispatch", work.dispatches || []],
				];
				const has_work = Number(work.total || 0) > 0 ||
					groups.some((group) => group[2].length);
				frm.toggle_display("ux_visit_work_tab", has_work);
				if (!has_work) return;
				frm.get_field("visit_work_summary").$wrapper.html(
					groups
						.filter((group) => group[2].length)
						.map((group) => render_visit_work_group(...group))
						.join("")
				);
			},
			error: () => {
				if (frm.doc.name !== visit_name) return;
				frm.toggle_display("ux_visit_work_tab", false);
				frappe.show_alert({
					message: __("Field Visit work could not be loaded. Check the server logs."),
					indicator: "red",
				}, 7);
			},
		});
	},
});

function render_visit_work_group(label, doctype, rows) {
	const items = rows.map((row) => {
		const link = frappe.utils.get_form_link(doctype, row.name);
		const title = frappe.utils.escape_html(row.title || row.name);
		const status = row.status
			? `<span class="indicator-pill ${visit_work_status_color(row.status)}">${frappe.utils.escape_html(row.status)}</span>`
			: "";
		const date = row.date
			? `<span class="text-muted small">${frappe.datetime.str_to_user(row.date)}</span>`
			: "";
		return `
			<a class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
				href="${link}">
				<div>
					<div class="font-weight-bold">${title}</div>
					<div class="text-muted small">${frappe.utils.escape_html(row.name)}</div>
				</div>
				<div class="d-flex flex-column align-items-end" style="gap: 0.35rem">${status}${date}</div>
			</a>`;
	}).join("");
	return `
		<div class="mb-4">
			<h5>${frappe.utils.escape_html(label)} <span class="text-muted">(${rows.length})</span></h5>
			<div class="list-group">${items}</div>
		</div>`;
}

function visit_work_status_color(status) {
	switch ((status || "").toLowerCase()) {
		case "completed":
		case "submitted":
		case "verified":
			return "green";
		case "cancelled":
			return "red";
		case "in progress":
		case "in_progress":
			return "orange";
		default:
			return "gray";
	}
}
