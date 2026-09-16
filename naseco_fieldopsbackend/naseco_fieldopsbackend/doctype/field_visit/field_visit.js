// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.ui.form.on("Field Visit", {
	refresh(frm) {
		frm.set_df_property("ux_visit_work_tab", "hidden", 1);
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
				];
				const has_work = groups.some((group) => group[2].length);
				frm.set_df_property("ux_visit_work_tab", "hidden", !has_work);
				if (!has_work) return;
				frm.get_field("visit_work_summary").$wrapper.html(
					groups
						.filter((group) => group[2].length)
						.map((group) => render_visit_work_group(...group))
						.join("")
				);
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
