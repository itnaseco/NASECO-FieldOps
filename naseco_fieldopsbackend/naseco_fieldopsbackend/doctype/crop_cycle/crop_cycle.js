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

		const can_confirm_planting = frappe.user_roles.some(
			(role) => ['Outgrower Manager', 'System Manager'].includes(role)
		);
		if (can_confirm_planting && frm.doc.planting_date && frm.doc.production_category && !frm.doc.planting_date_confirmed) {
			frm.add_custom_button(__('Confirm Planting Date'), () => confirm_planting_date(frm), __('Actions'));
		}

		add_related_record_buttons(frm);

		frm.add_custom_button(__('New Production Lot'), () => {
			frappe.new_doc('Crop Production Lot', {
				crop_cycle: frm.doc.name,
				production_contract: frm.doc.production_contract,
				plot: frm.doc.plot,
				season: frm.doc.season
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

		if (frm.doc.current_stage && frm.doc.recipe) {
			frm.add_custom_button(__('Request Current Stage Inputs'), () => {
				frappe.new_doc('Stage Input Request', {
					crop_cycle: frm.doc.name,
					stage: frm.doc.current_stage
				});
			}, __('Create'));
		}

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


function confirm_planting_date(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __('Confirm Planting Date'),
		fields: [
			{
				fieldtype: 'HTML',
				options: `<p>${__('Confirm planting for {0} on {1}? This will generate agronomy activities, reports and quality inspections.', [
					frappe.utils.escape_html(frm.doc.crop_cycle_id || frm.doc.name),
					frappe.datetime.str_to_user(frm.doc.planting_date)
				])}</p>`
			},
			{ fieldname: 'notes', fieldtype: 'Small Text', label: __('Confirmation Notes') }
		],
		primary_action_label: __('Confirm and Generate Schedules'),
		primary_action(values) {
			dialog.hide();
			frappe.call({
				method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle.confirm_planting_date',
				args: { crop_cycle: frm.doc.name, notes: values.notes },
				freeze: true,
				freeze_message: __('Confirming planting and generating schedules...'),
				callback() {
					frappe.show_alert({ message: __('Planting confirmed and schedules generated'), indicator: 'green' });
					frm.reload_doc();
				}
			});
		}
	});
	dialog.show();
}

function add_related_record_buttons(frm) {
	frappe.call({
		method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle.crop_cycle.get_related_record_counts',
		args: { crop_cycle: frm.doc.name },
		callback(r) {
			if (!r.message || frm.doc.__islocal) return;
			const counts = r.message;
			add_counted_button(frm, counts.inspections, __('View Inspections'), 'Inspection', 'Actions');
			add_counted_button(frm, counts.activities, __('View Agronomy Activities'), 'Stage Activity', 'Actions');
			add_counted_button(frm, counts.agronomy_reports, __('View Agronomy Reports'), 'Agronomy Report', 'Actions');
			add_counted_button(frm, counts.production_lots, __('View Production Lots'), 'Crop Production Lot', 'Harvest');
			add_counted_button(frm, counts.harvest_assessments, __('View Harvest Quality Assessments'), 'Seed Harvest Quality Assessment', 'Harvest');
			add_counted_button(frm, counts.input_requests, __('View Input Requests'), 'Stage Input Request', 'Finance');
			add_counted_button(frm, counts.advance_requests, __('View Advance Requests'), 'Crop Cycle Advance Request', 'Finance');
		}
	});
}

function add_counted_button(frm, count, label, doctype, group) {
	if (!count) return;
	frm.add_custom_button(__('{0} ({1})', [label, count]), () => {
		frappe.set_route('List', doctype, { crop_cycle: frm.doc.name });
	}, __(group));
}

function show_schedule_indicators(frm) {
	frm.dashboard.add_indicator(
		__('Production: {0}', [frm.doc.production_category || __('Not Set')]),
		frm.doc.production_category ? 'blue' : 'orange'
	);
	frm.dashboard.add_indicator(
		frm.doc.planting_date_confirmed ? __('Planting Date Confirmed') : __('Planting Date Not Confirmed'),
		frm.doc.planting_date_confirmed ? 'green' : 'orange'
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
