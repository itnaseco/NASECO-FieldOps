// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.ui.form.on("Crop Cycle", {
	setup(frm) {
		frm.set_query('production_contract', () => ({
			filters: {
				docstatus: 1,
				status: 'Active'
			}
		}));
	},

	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__('Open Production Contract'), () => {
			frappe.set_route('Form', 'Outgrower Production Contract', frm.doc.production_contract);
		}, __('Navigate'));

		const schedules_generated =
			frm.doc.inspection_schedule_generated && frm.doc.agronomy_schedule_generated;

		if (frm.doc.planting_date && frm.doc.production_category && !schedules_generated) {
			frm.add_custom_button(__('Generate Schedules'), () => generate_schedules(frm), __('Actions'));
		}

		if (frm.doc.inspection_schedule_generated) {
			frm.add_custom_button(__('View Inspections'), () => {
				frappe.set_route('List', 'Inspection', { crop_cycle: frm.doc.name });
			}, __('Actions'));
		}

		if (frm.doc.agronomy_schedule_generated) {
			frm.add_custom_button(__('View Agronomy Activities'), () => {
				frappe.set_route('List', 'Stage Activity', { crop_cycle: frm.doc.name });
			}, __('Actions'));
		}

		if (frm.doc.lifecycle_initialized) {
			frm.add_custom_button(__('View Agronomy Reports'), () => {
				frappe.set_route('List', 'Agronomy Report', { crop_cycle: frm.doc.name });
			}, __('Actions'));
		}

		frm.add_custom_button(__('View Production Lots'), () => {
			frappe.set_route('List', 'Crop Production Lot', { crop_cycle: frm.doc.name });
		}, __('Harvest'));

		frm.add_custom_button(__('New Production Lot'), () => {
			frappe.new_doc('Crop Production Lot', {
				crop_cycle: frm.doc.name,
				production_contract: frm.doc.production_contract,
				plot: frm.doc.plot,
				season: frm.doc.season
			});
		}, __('Harvest'));

		frm.add_custom_button(__('View Harvest Quality Assessments'), () => {
			frappe.set_route('List', 'Seed Harvest Quality Assessment', {
				crop_cycle: frm.doc.name
			});
		}, __('Harvest'));

		frm.add_custom_button(__('Refresh Financial Summary'), () => {
			frappe.call({
				method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle.refresh_financial_summary',
				args: { crop_cycle: frm.doc.name },
				freeze: true,
				callback() {
					frm.reload_doc();
				}
			});
		}, __('Finance'));

		if (!frm.doc.purchase_order) {
			frm.add_custom_button(__('Create Harvest Purchase Order'), () => {
				frappe.call({
					method: 'naseco_fieldopsbackend.fieldops_finance.create_crop_cycle_purchase_order',
					args: { crop_cycle: frm.doc.name },
					freeze: true,
					freeze_message: __('Creating harvest Purchase Order...'),
					callback(r) {
						if (r.message) {
							frappe.set_route('Form', 'Purchase Order', r.message);
						}
					}
				});
			}, __('Finance'));
		} else {
			frm.add_custom_button(__('Open Harvest Purchase Order'), () => {
				frappe.set_route('Form', 'Purchase Order', frm.doc.purchase_order);
			}, __('Finance'));
		}

		if (frm.doc.purchase_order) {
			frappe.db.get_value('Purchase Order', frm.doc.purchase_order, 'docstatus')
				.then(({ message }) => {
					if (message.docstatus === 1) {
						frm.add_custom_button(__('Request Cash Advance'), () => {
							frappe.new_doc('Crop Cycle Advance Request', {
								crop_cycle: frm.doc.name,
								company: frm.doc.company,
								purchase_order: frm.doc.purchase_order
							});
						}, __('Finance'));
					}
				});
		}

		frm.add_custom_button(__('View Input Requests'), () => {
			frappe.set_route('List', 'Stage Input Request', { crop_cycle: frm.doc.name });
		}, __('Finance'));

		if (frm.doc.current_stage && frm.doc.recipe) {
			frm.add_custom_button(__('Request Current Stage Inputs'), () => {
				frappe.new_doc('Stage Input Request', {
					crop_cycle: frm.doc.name,
					stage: frm.doc.current_stage
				});
			}, __('Create'));
		}

		frm.add_custom_button(__('View Advance Requests'), () => {
			frappe.set_route('List', 'Crop Cycle Advance Request', { crop_cycle: frm.doc.name });
		}, __('Finance'));

		frappe.db.get_value('Crop Cycle Settlement', { crop_cycle: frm.doc.name }, 'name')
			.then(({ message }) => {
				frm.add_custom_button(
					message?.name ? __('Open Settlement') : __('Prepare Settlement'),
					() => {
						if (message?.name) {
							frappe.set_route('Form', 'Crop Cycle Settlement', message.name);
						} else {
							frappe.new_doc('Crop Cycle Settlement', {
								crop_cycle: frm.doc.name,
								company: frm.doc.company,
								purchase_order: frm.doc.purchase_order
							});
						}
					},
					__('Finance')
				);
			});

		frm.add_custom_button(__('New Inspection'), () => {
			frappe.new_doc('Inspection', {
				crop_cycle: frm.doc.name,
				plot: frm.doc.plot,
				crop: frm.doc.crop,
				season: frm.doc.season,
				production_category: frm.doc.production_category
			});
		}, __('Create'));

		show_schedule_indicators(frm);
	}
});

function generate_schedules(frm) {
	frappe.call({
		method: 'naseco_fieldopsbackend.inspection_scheduler.generate_crop_cycle_schedules_for_doc',
		args: { crop_cycle: frm.doc.name },
		freeze: true,
		freeze_message: __('Generating QA and agronomy schedules...'),
		callback() {
			frappe.show_alert({ message: __('Schedules generated'), indicator: 'green' });
			frm.reload_doc();
		}
	});
}

function show_schedule_indicators(frm) {
	frm.dashboard.add_indicator(
		__('Production: {0}', [frm.doc.production_category || __('Not Set')]),
		frm.doc.production_category ? 'blue' : 'orange'
	);
	if (frm.doc.inspection_schedule_generated) {
		frm.dashboard.add_indicator(__('QA Schedule Generated'), 'green');
	}
	if (frm.doc.agronomy_schedule_generated) {
		frm.dashboard.add_indicator(__('Agronomy Schedule Generated'), 'green');
	}
	if (frm.doc.agronomy_report_schedule_generated) {
		frm.dashboard.add_indicator(__('Agronomy Reports Scheduled'), 'green');
	}
	if (frm.doc.expected_harvest_value) {
		frm.dashboard.add_indicator(
			__('Expected Harvest: {0}', [format_currency(frm.doc.expected_harvest_value, frm.doc.currency)]),
			'blue'
		);
	}
	if (frm.doc.total_exposure) {
		const exposureColor = frm.doc.forecast_net_payable < 0 ? 'red' : 'orange';
		frm.dashboard.add_indicator(
			__('Posted Exposure: {0}', [format_currency(frm.doc.total_exposure, frm.doc.currency)]),
			exposureColor
		);
	}
	if (frm.doc.forecast_net_payable || frm.doc.forecast_net_payable === 0) {
		frm.dashboard.add_indicator(
			__('Forecast Net Payable: {0}', [format_currency(frm.doc.forecast_net_payable, frm.doc.currency)]),
			frm.doc.forecast_net_payable >= 0 ? 'green' : 'red'
		);
	}
}
