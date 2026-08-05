// Copyright (c) 2026, NASECO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Agronomy Report', {
	setup(frm) {
		frm.set_query('stage', () => ({
			filters: { crop_cycle: frm.doc.crop_cycle }
		}));
	},

	refresh(frm) {
		configure_results_grid(frm);
		['report_template', 'crop_cycle', 'stage'].forEach((fieldname) => {
			frm.set_df_property(fieldname, 'read_only', !frm.is_new());
		});
		if (frm.is_new()) return;
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Record Observations'), () => {
				show_observation_dialog(frm);
			}, __('Actions'));
			frm.add_custom_button(__('Capture Current Location'), () => {
				capture_current_location(frm);
			}, __('Actions'));
		}
		if (frm.doc.crop_cycle) {
			frm.add_custom_button(__('Open Crop Cycle'), () => {
				frappe.set_route('Form', 'Crop Cycle', frm.doc.crop_cycle);
			}, __('Navigate'));
		}
		if (frm.doc.stage) {
			frm.add_custom_button(__('Open Crop Cycle Stage'), () => {
				frappe.set_route('Form', 'Crop Cycle Stage', frm.doc.stage);
			}, __('Navigate'));
		}
		frm.add_custom_button(__('View Stage Activities'), () => {
			frappe.set_route('List', 'Stage Activity', {
				crop_cycle: frm.doc.crop_cycle,
				stage: frm.doc.stage
			});
		}, __('Navigate'));
		if (frm.doc.overall_result && frm.doc.overall_result !== 'Not Evaluated') {
			frm.dashboard.add_indicator(
				__('Agronomy Result: {0}', [frm.doc.overall_result]),
				frm.doc.overall_result === 'Pass' ? 'green' : 'red'
			);
		}
	}
});

function configure_results_grid(frm) {
	const grid = frm.get_field('results')?.grid;
	if (!grid) return;
	grid.cannot_add_rows = true;
	grid.cannot_delete_rows = true;
	grid.df.cannot_add_rows = true;
	grid.df.cannot_delete_rows = true;
	grid.wrapper.find('.grid-add-row, .grid-remove-rows, .grid-delete-row').hide();
}

function show_observation_dialog(frm) {
	frappe.call({
		method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report.get_agronomy_observation_schema',
		args: { report: frm.doc.name },
		freeze: true,
		freeze_message: __('Loading agronomy observations...'),
		callback(r) {
			build_observation_dialog(frm, r.message || {});
		}
	});
}

function build_observation_dialog(frm, schema) {
	const fields = [];
	let current_section = null;
	(schema.attributes || []).forEach((attribute, index) => {
		if (attribute.section !== current_section) {
			current_section = attribute.section;
			fields.push({
				fieldtype: 'Section Break',
				label: __(current_section)
			});
		}
		fields.push({
			fieldname: `observation_${index}`,
			fieldtype: get_observation_fieldtype(attribute.data_type),
			label: attribute.unit
				? __('{0} ({1})', [attribute.label, attribute.unit])
				: __(attribute.label),
			options: get_observation_options(attribute),
			default: attribute.value,
			precision: ['Number', 'Percent'].includes(attribute.data_type) ? 4 : undefined
		});
		fields.push({
			fieldname: `remarks_${index}`,
			fieldtype: 'Small Text',
			label: __('Remarks'),
			default: attribute.remarks
		});
	});

	const dialog = new frappe.ui.Dialog({
		title: __('Record Agronomy Observations'),
		size: 'large',
		fields,
		primary_action_label: __('Save Observations'),
		primary_action(values) {
			const observations = (schema.attributes || []).map((attribute, index) => ({
				parameter_code: attribute.parameter_code,
				value: values[`observation_${index}`],
				remarks: values[`remarks_${index}`]
			}));
			dialog.get_primary_btn().prop('disabled', true);
			frappe.call({
				method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.agronomy_report.agronomy_report.save_agronomy_observations',
				args: {
					report: frm.doc.name,
					observations: JSON.stringify(observations)
				},
				freeze: true,
				freeze_message: __('Evaluating agronomy observations...'),
				callback() {
					dialog.hide();
					frm.reload_doc();
				},
				always() {
					dialog.get_primary_btn().prop('disabled', false);
				}
			});
		}
	});
	dialog.show();
}

function get_observation_fieldtype(data_type) {
	if (data_type === 'Count') return 'Int';
	if (['Number', 'Percent'].includes(data_type)) return 'Float';
	if (data_type === 'Date') return 'Date';
	if (['Yes/No', 'Good/Poor', 'Select'].includes(data_type)) return 'Select';
	if (data_type === 'Long Text') return 'Small Text';
	return 'Data';
}

function get_observation_options(attribute) {
	if (attribute.data_type === 'Yes/No') return '\nYes\nNo';
	if (attribute.data_type === 'Good/Poor') return '\nGood\nPoor';
	if (attribute.data_type === 'Select') {
		return `\n${(attribute.options || []).join('\n')}`;
	}
	return undefined;
}

function capture_current_location(frm) {
	if (!navigator.geolocation) {
		frappe.msgprint(__('Geolocation is not supported by this browser.'));
		return;
	}
	navigator.geolocation.getCurrentPosition(
		(position) => {
			const { latitude, longitude, accuracy } = position.coords;
			const location = {
				type: 'FeatureCollection',
				features: [{
					type: 'Feature',
					properties: { accuracy },
					geometry: { type: 'Point', coordinates: [longitude, latitude] }
				}]
			};
			frm.set_value({
				latitude,
				longitude,
				gps_accuracy_meters: accuracy,
				location_captured_at: frappe.datetime.now_datetime(),
				location: JSON.stringify(location)
			});
		},
		(error) => {
			frappe.msgprint(__('Could not capture location: {0}', [error.message]));
		},
		{ enableHighAccuracy: true, timeout: 30000, maximumAge: 0 }
	);
}
