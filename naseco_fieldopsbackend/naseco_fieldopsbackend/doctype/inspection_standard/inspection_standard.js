// Published inspection rules are historical records. Edit them only through
// a new draft template version so inspections already in the field stay stable.
frappe.ui.form.on('Inspection Standard', {
	async refresh(frm) {
		if (!frm.doc.inspection_template) return;
		const response = await frappe.db.get_value(
			'Inspection Template',
			frm.doc.inspection_template,
			['lifecycle_status', 'configuration_version']
		);
		const status = response.message?.lifecycle_status || 'Published';
		if (status === 'Draft') return;
		frm.set_intro(
			__('This standard belongs to a {0} template and is locked. Create a new template version to change it.', [status]),
			'orange'
		);
		for (const field of frm.meta.fields) {
			if (field.fieldname && !['Section Break', 'Column Break', 'Tab Break', 'HTML'].includes(field.fieldtype)) {
				frm.set_df_property(field.fieldname, 'read_only', 1);
			}
		}
	},
});
