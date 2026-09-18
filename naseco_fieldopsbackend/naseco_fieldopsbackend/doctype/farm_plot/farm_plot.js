// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.ui.form.on('Farm Plot', {
	refresh(frm) {
		configure_plot_id_entry(frm);
		// Add "View on Map" button if plot has vertices
		if (frm.doc.polygon && frm.doc.polygon.length >= 3) {
			frm.add_custom_button(__('View on Map'), function() {
				show_plot_map(frm);
			}, __('Actions'));
			if (!frm.is_new()) {
				frm.add_custom_button(__('Recalculate Plot Measurements'), function() {
					recalculate_plot_measurements(frm);
				}, __('Actions'));
			}
		}

		// Show summary of calculated values
		if (frm.doc.area_hectares || frm.doc.perimeter_meters) {
			frm.dashboard.add_indicator(
				__('Area: {0} hectares', [frm.doc.area_hectares || 0]),
				'blue'
			);
			frm.dashboard.add_indicator(
				__('Perimeter: {0} m', [frm.doc.perimeter_meters || 0]),
				'green'
			);
		}

		if (!frm.is_new()) {
			frappe.db.count('Inspection', { filters: { plot: frm.doc.name } }).then((count) => {
				if (!count) return;
				frm.add_custom_button(__('View Inspections ({0})', [count]), function() {
					frappe.set_route('List', 'Inspection', { plot: frm.doc.name });
				}, __('Actions'));
			});

			render_crop_cycles_section(frm);
		} else {
			clear_crop_cycles_section(frm);
		}
	},

	onload(frm) {
		enable_polygon_coordinate_entry(frm);
		configure_plot_id_entry(frm);
	},

	validate(frm) {
		renumber_polygon_vertices(frm);
	},

	polygon_move(frm) {
		renumber_polygon_vertices(frm);
		update_plot_geojson(frm);
	}
});

function configure_plot_id_entry(frm) {
	frappe.db.get_single_value('FieldOps Settings', 'auto_generate_plot_ids').then((enabled) => {
		const automatic = cint(enabled === null || enabled === undefined ? 1 : enabled);
		frm.set_df_property('plot_id', 'read_only', automatic);
		frm.set_df_property('plot_id', 'reqd', !automatic);
	});
}

frappe.ui.form.on('Plot Vertex', {
	polygon_add(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		row.order_index = (frm.doc.polygon || []).length;
		frm.refresh_field('polygon');
		update_plot_geojson(frm);
	},

	polygon_remove(frm) {
		renumber_polygon_vertices(frm);
		update_plot_geojson(frm);
	},

	latitude(frm) {
		update_plot_geojson(frm);
	},

	longitude(frm) {
		update_plot_geojson(frm);
	}
});

function enable_polygon_coordinate_entry(frm) {
	const grid = frm.fields_dict.polygon?.grid;
	if (!grid) return;

	grid.static_rows = false;
	grid.sortable_status = false;
	grid.refresh();
}

function renumber_polygon_vertices(frm) {
	let changed = false;
	(frm.doc.polygon || []).forEach((row, index) => {
		const order = index + 1;
		if (row.order_index !== order) {
			row.order_index = order;
			changed = true;
		}
	});
	if (changed) {
		frm.dirty();
		frm.refresh_field('polygon');
	}
}

function update_plot_geojson(frm) {
	const vertices = (frm.doc.polygon || []).filter((row) =>
		row.latitude !== null && row.latitude !== undefined && row.latitude !== '' &&
		row.longitude !== null && row.longitude !== undefined && row.longitude !== ''
	);

	if (vertices.length < 3) {
		frm.set_value('geojson', null);
		return;
	}

	const coordinates = vertices.map((row) => [Number(row.longitude), Number(row.latitude)]);
	if (coordinates[coordinates.length - 1][0] !== coordinates[0][0] ||
		coordinates[coordinates.length - 1][1] !== coordinates[0][1]) {
		coordinates.push([...coordinates[0]]);
	}

	frm.set_value('geojson', JSON.stringify({
		type: 'Feature',
		geometry: { type: 'Polygon', coordinates: [coordinates] },
		properties: {
			plot_id: frm.doc.plot_id,
			plot_name: frm.doc.plot_name || '',
			area_hectares: frm.doc.area_hectares || 0,
			perimeter_meters: frm.doc.perimeter_meters || 0
		}
	}, null, 2));
}

function recalculate_plot_measurements(frm) {
	const calculate = () => {
		frappe.call({
			method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.farm_plot.farm_plot.recalculate_plot_measurements',
			args: { farm_plot: frm.doc.name },
			freeze: true,
			freeze_message: __('Calculating plot measurements...'),
			callback() {
				frm.reload_doc();
			}
		});
	};

	if (frm.is_dirty()) {
		frm.save().then(calculate);
	} else {
		calculate();
	}
}

function render_crop_cycles_section(frm) {
	const wrapper = get_crop_cycles_wrapper(frm);
	if (!wrapper) return;

	frm.remove_custom_button(__('New Production Contract'), __('Create'));
	frm.remove_custom_button(__('Open Crop Cycle'), __('Actions'));
	wrapper.html(`
		<div class="text-muted small" style="padding: 12px 0;">
			${__('Loading crop cycles...')}
		</div>
	`);

	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'Crop Cycle',
			filters: {
				plot: frm.doc.name
			},
			fields: [
				'name',
				'crop_cycle_id',
				'crop',
				'variety',
				'season',
				'planting_date',
				'expected_harvest_date',
				'production_category',
				'current_stage',
				'status'
			],
			order_by: 'planting_date desc, creation desc',
			limit_page_length: 1000
		},
		callback(r) {
			display_crop_cycles(frm, r.message || []);
		},
		error() {
			wrapper.html(`
				<div class="text-muted small" style="padding: 12px 0;">
					${__('Unable to load crop cycles.')}
				</div>
			`);
		}
	});
}

function display_crop_cycles(frm, crop_cycles) {
	const wrapper = get_crop_cycles_wrapper(frm);
	if (!wrapper) return;

	if (!crop_cycles.length) {
		add_new_crop_cycle_button(frm);
		wrapper.html(`
			<div class="text-muted" style="padding: 16px 0;">
				<div style="margin-bottom: 10px;">${__('No crop cycles have been registered for this farm plot.')}</div>
				<button type="button" class="btn btn-sm btn-primary create-production-contract">
					${__('New Production Contract')}
				</button>
			</div>
		`);
		wrapper.find('.create-production-contract').on('click', () => {
			frappe.new_doc('Outgrower Production Contract', {
				farm_plot: frm.doc.name,
				outgrower: frm.doc.outgrower
			});
		});
		return;
	}

	const assigned_cycle = crop_cycles[0];
	frm.add_custom_button(__('Open Crop Cycle'), () => {
		frappe.set_route('Form', 'Crop Cycle', assigned_cycle.name);
	}, __('Actions'));
	frm.dashboard.add_indicator(
		__('Crop Cycle: {0}', [assigned_cycle.crop_cycle_id || assigned_cycle.name]),
		'blue'
	);

	const rows = crop_cycles.map((cycle, index) => {
		const status = cycle.status || 'PLANNED';
		const status_color = {
			ACTIVE: 'green',
			COMPLETED: 'blue',
			PLANNED: 'orange'
		}[status] || 'gray';
		const crop_name = escape_html(cycle.crop || __('Crop not set'));
		const variety = cycle.variety
			? `<span class="text-muted"> · ${escape_html(cycle.variety)}</span>`
			: '';

		return `
			<tr>
				<td>
					<button type="button" class="btn btn-link btn-sm open-crop-cycle"
						data-cycle-index="${index}" style="padding: 0; text-align: left;">
						${escape_html(cycle.crop_cycle_id || cycle.name)}
					</button>
					<div class="small">${crop_name}${variety}</div>
				</td>
				<td>${escape_html(cycle.season || '-')}</td>
				<td>${format_date(cycle.planting_date)}</td>
				<td>${escape_html(cycle.production_category || '-')}</td>
				<td>${escape_html(cycle.current_stage || '-')}</td>
				<td>
					<span class="indicator-pill ${status_color}">${escape_html(__(status))}</span>
				</td>
			</tr>
		`;
	}).join('');

	wrapper.html(`
		<div class="text-muted small" style="padding: 4px 0 10px;">
			${__('Assigned Crop Cycle')}
		</div>
		<div class="table-responsive">
			<table class="table table-bordered table-hover" style="margin-bottom: 0;">
				<thead>
					<tr>
						<th>${__('Cycle / Crop')}</th>
						<th>${__('Season')}</th>
						<th>${__('Planting Date')}</th>
						<th>${__('Category')}</th>
						<th>${__('Current Stage')}</th>
						<th>${__('Status')}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		</div>
	`);

	wrapper.find('.open-crop-cycle').on('click', function() {
		const cycle = crop_cycles[Number($(this).data('cycle-index'))];
		if (cycle) {
			frappe.set_route('Form', 'Crop Cycle', cycle.name);
		}
	});
}

function add_new_crop_cycle_button(frm) {
	frm.add_custom_button(__('New Production Contract'), () => {
		frappe.new_doc('Outgrower Production Contract', {
			farm_plot: frm.doc.name,
			outgrower: frm.doc.outgrower
		});
	}, __('Create'));
}

function clear_crop_cycles_section(frm) {
	const wrapper = get_crop_cycles_wrapper(frm);
	if (wrapper) wrapper.empty();
}

function get_crop_cycles_wrapper(frm) {
	return frm.fields_dict.crop_cycles_html?.$wrapper || null;
}

function format_date(value) {
	return value ? frappe.datetime.str_to_user(value) : '-';
}

function escape_html(value) {
	return frappe.utils.escape_html(String(value ?? ''));
}


function show_plot_map(frm) {
	frappe.require('/assets/naseco_fieldopsbackend/js/plot_map_dialog.js').then(() => {
		naseco_fieldopsbackend.show_plot_map_dialog(frm.doc);
	});
}
