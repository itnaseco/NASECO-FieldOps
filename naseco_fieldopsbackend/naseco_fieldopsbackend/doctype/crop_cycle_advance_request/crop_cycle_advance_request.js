// Copyright (c) 2026, NASECO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Crop Cycle Advance Request', {
	refresh(frm) {
		show_exposure_indicators(frm);
		if (frm.is_new()) return;

		frm.add_custom_button(__('Refresh Exposure'), () => {
			frappe.call({
				method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_advance_request.crop_cycle_advance_request.refresh_exposure',
				args: { advance_request: frm.doc.name },
				freeze: true,
				callback() {
					frm.reload_doc();
				}
			});
		}, __('Actions'));

		if (frm.doc.payment_entry) {
			frm.add_custom_button(__('Open Payment Entry'), () => {
				frappe.set_route('Form', 'Payment Entry', frm.doc.payment_entry);
			}, __('Payments'));
		} else if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Create Payment Entry'), () => {
				frappe.call({
					method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_advance_request.crop_cycle_advance_request.create_payment_entry',
					args: { advance_request: frm.doc.name },
					freeze: true,
					callback(r) {
						if (r.message) {
							frappe.set_route('Form', 'Payment Entry', r.message);
						}
					}
				});
			}, __('Payments'));
		}

		frm.add_custom_button(__('Open Crop Cycle'), () => {
			frappe.set_route('Form', 'Crop Cycle', frm.doc.crop_cycle);
		}, __('Navigate'));
	},

	crop_cycle(frm) {
		if (!frm.doc.crop_cycle || !frm.is_new()) return;
		frappe.call({
			method: 'naseco_fieldopsbackend.fieldops_finance.calculate_crop_cycle_exposure',
			args: { crop_cycle: frm.doc.crop_cycle },
			callback(r) {
				if (!r.message) return;
				[
					'expected_harvest_value',
					'risk_adjusted_harvest_value',
					'recoverable_stock_value',
					'cash_advanced',
					'pending_cash_advance',
					'exposure_limit',
					'available_advance_capacity'
				].forEach((fieldname) => frm.set_value(fieldname, r.message[fieldname]));
			}
		});
	}
});

function show_exposure_indicators(frm) {
	if (!frm.doc.currency) return;
	frm.dashboard.add_indicator(
		__('Available Capacity: {0}', [
			format_currency(frm.doc.available_advance_capacity || 0, frm.doc.currency)
		]),
		(frm.doc.available_advance_capacity || 0) > 0 ? 'green' : 'red'
	);
	frm.dashboard.add_indicator(
		__('Current Cash Advances: {0}', [
			format_currency(frm.doc.cash_advanced || 0, frm.doc.currency)
		]),
		'blue'
	);
}
