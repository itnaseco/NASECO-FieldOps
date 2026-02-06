// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stage Input Request', {
	refresh(frm) {
		// Show fulfillment progress indicator
		show_fulfillment_progress(frm);

		// Add "Create Dispatch" button if not fully fulfilled
		if (frm.doc.status !== 'Fulfilled' && frm.doc.status !== 'Rejected') {
			frm.add_custom_button(__('Create Dispatch'), function() {
				create_dispatch(frm);
			});
		}

		// Add "View Dispatches" button
		if (!frm.is_new()) {
			frm.add_custom_button(__('View Dispatches'), function() {
				frappe.set_route('List', 'Stage Input Dispatch', {
					'input_request': frm.doc.name
				});
			});
		}
	},

	quantity_needed(frm) {
		update_remaining_quantity(frm);
	},

	quantity_dispatched(frm) {
		update_remaining_quantity(frm);
	}
});

function show_fulfillment_progress(frm) {
	if (!frm.doc.quantity_needed) return;

	let quantity_needed = frm.doc.quantity_needed || 0;
	let quantity_dispatched = frm.doc.quantity_dispatched || 0;
	let percentage = (quantity_dispatched / quantity_needed) * 100;

	// Determine color based on fulfillment percentage
	let indicator_color = 'red';
	if (percentage >= 100) {
		indicator_color = 'green';
	} else if (percentage > 0) {
		indicator_color = 'orange';
	}

	// Add dashboard indicators
	frm.dashboard.add_indicator(
		__('Fulfillment: {0}%', [percentage.toFixed(1)]),
		indicator_color
	);

	frm.dashboard.add_indicator(
		__('Dispatched: {0} / {1}', [quantity_dispatched, quantity_needed]),
		indicator_color
	);

	// Show remaining quantity
	if (frm.doc.quantity_remaining > 0) {
		frm.dashboard.add_indicator(
			__('Remaining: {0}', [frm.doc.quantity_remaining]),
			'blue'
		);
	}
}

function update_remaining_quantity(frm) {
	let quantity_needed = frm.doc.quantity_needed || 0;
	let quantity_dispatched = frm.doc.quantity_dispatched || 0;
	frm.set_value('quantity_remaining', quantity_needed - quantity_dispatched);
}

function create_dispatch(frm) {
	// Open new dispatch form with pre-filled values
	frappe.new_doc('Stage Input Dispatch', {
		'input_request': frm.doc.name,
		'crop_cycle': frm.doc.crop_cycle,
		'stage': frm.doc.stage,
		'input_name': frm.doc.input_name,
		'unit': frm.doc.unit,
		'quantity_dispatched': frm.doc.quantity_remaining || 0
	});
}
