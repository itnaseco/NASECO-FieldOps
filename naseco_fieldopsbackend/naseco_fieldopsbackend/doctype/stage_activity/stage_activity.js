// Copyright (c) 2026, NASECO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stage Activity', {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.crop_cycle) {
			frm.add_custom_button(__('Open Crop Cycle'), () => {
				frappe.set_route('Form', 'Crop Cycle', frm.doc.crop_cycle);
			}, __('Navigate'));
		}
		if (frm.doc.stage) {
			frappe.db.get_value('Crop Cycle Stage', frm.doc.stage, 'agronomy_report')
				.then(({ message }) => {
					if (!message?.agronomy_report) return;
					frm.add_custom_button(__('Open Agronomy Report'), () => {
						frappe.set_route('Form', 'Agronomy Report', message.agronomy_report);
					}, __('Navigate'));
				});
		}

		frm.add_custom_button(__('Create Field Visit'), () => {
			frappe.new_doc('Field Visit', {
				crop_cycle: frm.doc.crop_cycle,
				stage: frm.doc.stage,
				scheduled_date: frm.doc.activity_date
			});
		}, __('Create'));
	}
});
