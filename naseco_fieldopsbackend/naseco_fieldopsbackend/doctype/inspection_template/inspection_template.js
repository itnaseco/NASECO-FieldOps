// Copyright (c) 2026, NASECO and contributors

frappe.ui.form.on('Inspection Template', {
	validate(frm) {
		const seen = new Set();
		for (const row of frm.doc.quality_parameters || []) {
			if (!row.active) continue;
			const key = [row.parameter, row.production_category || '', row.seed_class || ''].join('|');
			if (seen.has(key)) {
				frappe.throw(__('Parameter {0} is duplicated for the same production category and seed class.', [row.parameter]));
			}
			seen.add(key);
		}
	},
	refresh(frm) {
		const status = frm.doc.lifecycle_status || 'Published';
		const isManager = frappe.user_roles.includes('Quality Manager') || frappe.user_roles.includes('System Manager');
		frm.set_intro(
			status === 'Draft'
				? __('This draft can be edited safely. Existing inspections continue using their frozen configuration.')
				: __('Published and retired versions are historical configuration. Create a new version to change their rules.'),
			status === 'Draft' ? 'blue' : 'orange'
		);
		if (status !== 'Draft') {
			for (const field of frm.meta.fields) {
				if (field.fieldname && !['Section Break', 'Column Break', 'Tab Break', 'HTML'].includes(field.fieldtype)) {
					frm.set_df_property(field.fieldname, 'read_only', 1);
				}
		}
		if (status === 'Draft') {
			frm.set_intro(
				__('Define inspection-level and take-level parameters under Parameters and Standards, then define crop/region/plot selection under Applicability Rules.'),
				'blue'
			);
		}
		}
		if (!isManager || frm.is_new()) return;
		if (status === 'Draft') {
			frm.add_custom_button(__('Publish Version'), () => {
				frappe.call({
					method: 'naseco_fieldopsbackend.api.publish_inspection_template_version',
					args: { template: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			}, __('Configuration'));
		} else if (status === 'Published') {
			frm.add_custom_button(__('Create New Version'), () => {
				frappe.call({
					method: 'naseco_fieldopsbackend.api.create_inspection_template_version',
					args: { template: frm.doc.name },
					freeze: true,
					callback: (response) => {
						if (response.message?.name) {
							frappe.set_route('Form', 'Inspection Template', response.message.name);
						}
					},
				});
			}, __('Configuration'));
		}
	},
});
