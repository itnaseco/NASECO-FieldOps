// Copyright (c) 2026, NASECO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Field Corrective Action', {
	refresh(frm) {
		frm.set_query('assigned_to', () => ({
			query: 'naseco_fieldopsbackend.roles.user_with_role_query',
			filters: { role: 'Outgrower Supervisor' }
		}));
		frm.set_query('verification_assigned_to', () => ({
			query: 'naseco_fieldopsbackend.roles.user_with_role_query',
			filters: { role: 'Quality Inspector' }
		}));

		if (frm.doc.inspection) {
			frm.add_custom_button(__('Open Inspection'), () => {
				frappe.set_route('Form', 'Inspection', frm.doc.inspection);
			}, __('Navigate'));
		}
		if (frm.doc.crop_cycle) {
			frm.add_custom_button(__('Open Crop Cycle'), () => {
				frappe.set_route('Form', 'Crop Cycle', frm.doc.crop_cycle);
			}, __('Navigate'));
		}
	}
});
