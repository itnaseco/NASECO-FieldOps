// Parameters referenced by published standards must be replaced, not edited,
// because their data type and calculation method define historical results.
frappe.ui.form.on('Inspection Parameter', {
	async refresh(frm) {
		if (frm.is_new()) return;
		const standards = await frappe.db.get_list('Inspection Standard', {
			filters: { parameter: frm.doc.name },
			fields: ['inspection_template'],
			limit: 100,
		});
		if (!standards.length) return;
		const templates = [...new Set(standards.map(row => row.inspection_template).filter(Boolean))];
		const published = await frappe.db.get_list('Inspection Template', {
			filters: { name: ['in', templates], lifecycle_status: 'Published' },
			fields: ['name'],
			limit: 1,
		});
		if (!published.length) return;
		frm.set_intro(
			__('This parameter is used by a published template and is locked. Create a new parameter for changed measurement semantics.'),
			'orange'
		);
		for (const field of frm.meta.fields) {
			if (field.fieldname && !['Section Break', 'Column Break', 'Tab Break', 'HTML'].includes(field.fieldtype)) {
				frm.set_df_property(field.fieldname, 'read_only', 1);
			}
		}
	},
});
