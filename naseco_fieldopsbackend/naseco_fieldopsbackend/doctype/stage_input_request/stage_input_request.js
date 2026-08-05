// Copyright (c) 2026, NASECO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stage Input Request', {
	setup(frm) {
		frm.set_query('source_warehouse', () => ({
			filters: { company: frm.doc.company, is_group: 0, disabled: 0 }
		}));
		frm.set_query('stage', () => ({
			filters: { crop_cycle: frm.doc.crop_cycle }
		}));
	},

	refresh(frm) {
		show_fulfillment_progress(frm);
		if (frm.is_new()) return;

		if (frm.doc.material_request) {
			frm.add_custom_button(__('Open Material Request'), () => {
				frappe.set_route('Form', 'Material Request', frm.doc.material_request);
			}, __('Stock Operations'));

			frm.add_custom_button(__('View Stock Entries'), () => {
				frappe.set_route('List', 'Stock Entry', {
					custom_stage_input_request: frm.doc.name
				});
			}, __('Stock Operations'));
		} else if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Create Material Request'), () => {
				frappe.call({
					method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.stage_input_request.stage_input_request.create_material_request',
					args: { input_request: frm.doc.name },
					freeze: true,
					callback(r) {
						if (r.message) {
							frappe.set_route('Form', 'Material Request', r.message);
						}
					}
				});
			}, __('Stock Operations'));
		}

		frm.add_custom_button(__('Refresh Fulfilment'), () => {
			frappe.call({
				method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.stage_input_request.stage_input_request.refresh_fulfillment',
				args: { input_request: frm.doc.name },
				freeze: true,
				callback() {
					frm.reload_doc();
				}
			});
		}, __('Actions'));

		frm.add_custom_button(__('Open Crop Cycle'), () => {
			frappe.set_route('Form', 'Crop Cycle', frm.doc.crop_cycle);
		}, __('Navigate'));
	},

	crop_cycle(frm) {
		if (!frm.doc.crop_cycle) return;
		frappe.db.get_value(
			'Crop Cycle',
			frm.doc.crop_cycle,
			['company', 'recipe']
		).then((r) => {
			if (r.message?.company) {
				frm.set_value('company', r.message.company);
			}
			if (r.message?.recipe && !(frm.doc.items || []).length) {
				load_recipe_inputs(frm);
			}
		});
	},

	stage(frm) {
		if (frm.doc.crop_cycle && !(frm.doc.items || []).length) {
			load_recipe_inputs(frm);
		}
	}
});

frappe.ui.form.on('Stage Input Request Item', {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) return;
		frappe.db.get_value('Item', row.item_code, ['item_name', 'stock_uom', 'valuation_rate'])
			.then((r) => {
				if (!r.message) return;
				frappe.model.set_value(cdt, cdn, 'item_name', r.message.item_name);
				frappe.model.set_value(cdt, cdn, 'uom', r.message.stock_uom);
				frappe.model.set_value(cdt, cdn, 'stock_uom', r.message.stock_uom);
				frappe.model.set_value(cdt, cdn, 'conversion_factor', 1);
				frappe.model.set_value(cdt, cdn, 'estimated_rate', r.message.valuation_rate || 0);
				update_line_amount(frm, cdt, cdn);
			});
	},
	uom(frm, cdt, cdn) {
		resolve_uom_conversion(frm, cdt, cdn);
	},
	requested_qty: update_line_amount,
	approved_qty: update_line_amount,
	estimated_rate: update_line_amount,
	recovery_policy(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.recovery_policy === 'Fully Recoverable') {
			frappe.model.set_value(cdt, cdn, 'recoverable_percent', 100);
		} else if (['Company Subsidy', 'Non-Recoverable'].includes(row.recovery_policy)) {
			frappe.model.set_value(cdt, cdn, 'recoverable_percent', 0);
		}
	}
});

function update_line_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	row.requested_stock_qty = flt(row.requested_qty || 0) * flt(row.conversion_factor || 1);
	row.approved_stock_qty = flt(row.approved_qty || 0) * flt(row.conversion_factor || 1);
	row.estimated_amount = row.approved_stock_qty * flt(row.estimated_rate || 0);
	row.issued_qty = flt(row.issued_stock_qty || 0) / flt(row.conversion_factor || 1);
	row.remaining_qty = Math.max(flt(row.approved_qty || 0) - flt(row.issued_qty || 0), 0);
	row.remaining_stock_qty = Math.max(row.approved_stock_qty - flt(row.issued_stock_qty || 0), 0);
	frm.refresh_field('items');
	update_totals(frm);
}

function update_totals(frm) {
	const rows = frm.doc.items || [];
	frm.set_value(
		'total_requested_value',
		rows.reduce((total, row) => total + flt(row.requested_stock_qty) * flt(row.estimated_rate), 0)
	);
	frm.set_value(
		'total_approved_value',
		rows.reduce((total, row) => total + flt(row.approved_stock_qty) * flt(row.estimated_rate), 0)
	);
}

function resolve_uom_conversion(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.item_code || !row.uom) return;
	frappe.call({
		method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.stage_input_request.stage_input_request.get_item_uom_details',
		args: { item_code: row.item_code, uom: row.uom },
		callback({ message }) {
			if (!message) return;
			frappe.model.set_value(cdt, cdn, 'stock_uom', message.stock_uom);
			frappe.model.set_value(cdt, cdn, 'conversion_factor', message.conversion_factor);
			update_line_amount(frm, cdt, cdn);
		}
	});
}

function load_recipe_inputs(frm) {
	frappe.call({
		method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.stage_input_request.stage_input_request.get_recipe_input_plan',
		args: {
			crop_cycle: frm.doc.crop_cycle,
			stage: frm.doc.stage
		},
		callback: ({ message: rows }) => {
			if ((frm.doc.items || []).length) return;
			(rows || []).forEach((row) => {
				const child = frm.add_child('items');
				Object.assign(child, row);
				child.source_warehouse = row.source_warehouse || frm.doc.source_warehouse;
			});
			frm.refresh_field('items');
		}
	});
}

function show_fulfillment_progress(frm) {
	const rows = frm.doc.items || [];
	const approved = rows.reduce((total, row) => total + flt(row.approved_qty), 0);
	const issued = rows.reduce((total, row) => total + flt(row.issued_qty), 0);
	if (!approved) return;
	const percent = Math.min((issued / approved) * 100, 100);
	frm.dashboard.add_indicator(
		__('Stock Fulfilment: {0}%', [percent.toFixed(1)]),
		percent >= 100 ? 'green' : issued > 0 ? 'orange' : 'red'
	);
}
