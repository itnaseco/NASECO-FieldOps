// Copyright (c) 2026, NASECO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Crop Cycle Stage', {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__('Open Crop Cycle'), () => {
			frappe.set_route('Form', 'Crop Cycle', frm.doc.crop_cycle);
		}, __('Navigate'));
		if (frm.doc.agronomy_report) {
			frm.add_custom_button(__('Open Agronomy Report'), () => {
				frappe.set_route('Form', 'Agronomy Report', frm.doc.agronomy_report);
			}, __('Navigate'));
		}
		frm.add_custom_button(__('View Activities'), () => {
			frappe.set_route('List', 'Stage Activity', { stage: frm.doc.name });
		}, __('Navigate'));
		frm.add_custom_button(__('Request Inputs'), () => {
			frappe.new_doc('Stage Input Request', {
				crop_cycle: frm.doc.crop_cycle,
				stage: frm.doc.name
			});
		}, __('Create'));
	}
});
