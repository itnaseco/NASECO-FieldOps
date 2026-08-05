// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.ui.form.on('Farm Plot', {
	refresh(frm) {
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
		if (frm.doc.area_acres || frm.doc.perimeter_meters) {
			frm.dashboard.add_indicator(
				__('Area: {0} acres', [frm.doc.area_acres || 0]),
				'blue'
			);
			frm.dashboard.add_indicator(
				__('Perimeter: {0} m', [frm.doc.perimeter_meters || 0]),
				'green'
			);
		}

		if (!frm.is_new()) {
			frm.add_custom_button(__('View Inspections'), function() {
				frappe.set_route('List', 'Inspection', {
					plot: frm.doc.name
				});
			}, __('Actions'));

			render_crop_cycles_section(frm);
		} else {
			clear_crop_cycles_section(frm);
		}
	},

	onload(frm) {
		enable_polygon_coordinate_entry(frm);
	},

	validate(frm) {
		renumber_polygon_vertices(frm);
	},

	polygon_move(frm) {
		renumber_polygon_vertices(frm);
	}
});

frappe.ui.form.on('Plot Vertex', {
	polygon_add(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		row.order_index = (frm.doc.polygon || []).length;
		frm.refresh_field('polygon');
	},

	polygon_remove(frm) {
		renumber_polygon_vertices(frm);
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
	// Get vertices
	let vertices = frm.doc.polygon || [];

	if (vertices.length < 3) {
		frappe.msgprint(__('Plot must have at least 3 vertices to display on map'));
		return;
	}

	// Sort vertices by order_index to ensure correct polygon shape
	vertices.sort((a, b) => a.order_index - b.order_index);

	let coordinates = vertices.map(v => [parseFloat(v.latitude), parseFloat(v.longitude)]);

	// Calculate center for map
	let centerLat = frm.doc.centroid_lat || coordinates[0][0];
	let centerLng = frm.doc.centroid_lng || coordinates[0][1];

	// Create dialog with map
	let d = new frappe.ui.Dialog({
		title: __('Plot Map: {0}', [frm.doc.plot_name || frm.doc.plot_id]),
		size: 'extra-large',
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'map_html'
			}
		]
	});

	d.show();

	// Wait for dialog to render, then create map
	setTimeout(function() {
		// Create map container HTML with legend
		let map_container = `
			<div style="position: relative;">
				<div id="plot_map_container" style="height: 700px; width: 100%; border: 1px solid #ddd; border-radius: 4px;"></div>
				<div id="map_legend" style="position: absolute; bottom: 20px; left: 20px; background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 1000; max-width: 250px;">
					<h5 style="margin: 0 0 10px 0; font-size: 14px; font-weight: bold;">📍 Map Legend</h5>
					<div style="display: flex; align-items: center; margin: 8px 0;">
						<div style="width: 20px; height: 3px; background: #3388ff; margin-right: 10px;"></div>
						<span style="font-size: 12px;">Plot Boundary</span>
					</div>
					<div style="display: flex; align-items: center; margin: 8px 0;">
						<div style="width: 12px; height: 12px; background: #ff7800; border: 2px solid white; border-radius: 50%; margin-right: 10px;"></div>
						<span style="font-size: 12px;">Vertices</span>
					</div>
					<div style="display: flex; align-items: center; margin: 8px 0;">
						<div style="width: 16px; height: 20px; background: #dc3545; clip-path: polygon(50% 0%, 100% 100%, 0% 100%); margin-right: 10px;"></div>
						<span style="font-size: 12px;">Centroid</span>
					</div>
					<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ddd;">
						<div style="font-size: 11px; color: #666;">
							<strong>Area:</strong> ${(frm.doc.area_acres || 0).toFixed(3)} acres<br>
							<strong>Perimeter:</strong> ${(frm.doc.perimeter_meters || 0).toFixed(1)} m
						</div>
					</div>
				</div>
			</div>
			<style>
				.leaflet-container {
					height: 100%;
					width: 100%;
				}
				.leaflet-control-layers {
					border: 2px solid rgba(0,0,0,0.2);
					border-radius: 8px;
				}
			</style>
		`;

		d.fields_dict.map_html.$wrapper.html(map_container);

		// Load Leaflet CSS if not already loaded
		if (!document.getElementById('leaflet-css')) {
			let link = document.createElement('link');
			link.id = 'leaflet-css';
			link.rel = 'stylesheet';
			link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
			document.head.appendChild(link);
		}

		// Load Leaflet JS if not already loaded
		if (typeof L === 'undefined') {
			let script = document.createElement('script');
			script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
			script.onload = function() {
				render_map();
			};
			document.head.appendChild(script);
		} else {
			render_map();
		}

		function render_map() {
			// Wait a bit more for container to be fully rendered
			setTimeout(function() {
				try {
					// Initialize map
					let map = L.map('plot_map_container', {
						zoomControl: true,
						attributionControl: true
					}).setView([centerLat, centerLng], 17);

					// Define base layers with different map types
					let baseLayers = {
						"🛰️ Satellite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
							attribution: 'Tiles © Esri',
							maxZoom: 19
						}),
						"🗺️ Street Map": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
							attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
							maxZoom: 19
						}),
						"🏞️ Terrain": L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
							attribution: '© <a href="https://opentopomap.org">OpenTopoMap</a>',
							maxZoom: 17
						}),
						"🌐 Hybrid": L.layerGroup([
							L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
								attribution: 'Tiles © Esri',
								maxZoom: 19
							}),
							L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}.png', {
								attribution: '© CartoDB',
								maxZoom: 19,
								pane: 'shadowPane'
							})
						])
					};

					// Add default satellite layer
					baseLayers["🛰️ Satellite"].addTo(map);

					// Add layer control
					L.control.layers(baseLayers, null, {
						position: 'topright',
						collapsed: false
					}).addTo(map);

					// Add scale control
					L.control.scale({
						position: 'bottomright',
						imperial: false,
						metric: true
					}).addTo(map);

					// Draw polygon with enhanced styling
					let polygon = L.polygon(coordinates, {
						color: '#3388ff',
						fillColor: '#3388ff',
						fillOpacity: 0.25,
						weight: 3,
						dashArray: '5, 5',
						className: 'plot-polygon'
					}).addTo(map);

					// Add area label to polygon
					let polygonCenter = polygon.getBounds().getCenter();
					let areaLabel = L.divIcon({
						className: 'area-label',
						html: `<div style="background: rgba(51, 136, 255, 0.9); color: white; padding: 8px 12px; border-radius: 4px; font-size: 13px; font-weight: bold; white-space: nowrap; box-shadow: 0 2px 8px rgba(0,0,0,0.3);">
							${(frm.doc.area_acres || 0).toFixed(3)} acres
						</div>`,
						iconSize: [100, 30],
						iconAnchor: [50, 15]
					});
					L.marker(polygonCenter, { icon: areaLabel }).addTo(map);

					// Add markers for each vertex with enhanced styling
					coordinates.forEach((coord, index) => {
						L.circleMarker(coord, {
							radius: 8,
							fillColor: '#ff7800',
							color: '#fff',
							weight: 3,
							opacity: 1,
							fillOpacity: 0.9
						}).addTo(map).bindPopup(`
							<div style="font-family: sans-serif; min-width: 150px;">
								<h5 style="margin: 0 0 8px 0; color: #ff7800;">📍 Vertex ${index + 1}</h5>
								<div style="font-size: 12px;">
									<strong>Latitude:</strong> ${coord[0].toFixed(6)}<br>
									<strong>Longitude:</strong> ${coord[1].toFixed(6)}
								</div>
							</div>
						`);

						// Add vertex labels
						let label = L.divIcon({
							className: 'vertex-label',
							html: `<div style="background: white; color: #ff7800; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: bold; border: 2px solid #ff7800;">${index + 1}</div>`,
							iconSize: [20, 20],
							iconAnchor: [10, 25]
						});
						L.marker(coord, { icon: label }).addTo(map);
					});

					// Add centroid marker with enhanced styling
					if (frm.doc.centroid_lat && frm.doc.centroid_lng) {
						L.marker([centerLat, centerLng], {
							icon: L.icon({
								iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
								shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
								iconSize: [30, 45],
								iconAnchor: [15, 45],
								popupAnchor: [1, -34],
								shadowSize: [45, 45]
							})
						}).addTo(map).bindPopup(`
							<div style="font-family: sans-serif; min-width: 200px;">
								<h4 style="margin: 0 0 12px 0; color: #dc3545; border-bottom: 2px solid #dc3545; padding-bottom: 8px;">
									📍 ${frm.doc.plot_name || frm.doc.plot_id}
								</h4>
								<table style="width: 100%; font-size: 12px; border-collapse: collapse;">
									<tr style="border-bottom: 1px solid #eee;">
										<td style="padding: 6px 0;"><strong>📐 Area:</strong></td>
										<td style="padding: 6px 0; text-align: right;">${(frm.doc.area_acres || 0).toFixed(3)} acres</td>
									</tr>
									<tr style="border-bottom: 1px solid #eee;">
										<td style="padding: 6px 0;"><strong>📏 Perimeter:</strong></td>
										<td style="padding: 6px 0; text-align: right;">${(frm.doc.perimeter_meters || 0).toFixed(1)} m</td>
									</tr>
									<tr style="border-bottom: 1px solid #eee;">
										<td style="padding: 6px 0;"><strong>📌 Vertices:</strong></td>
										<td style="padding: 6px 0; text-align: right;">${coordinates.length}</td>
									</tr>
									<tr style="border-bottom: 1px solid #eee;">
										<td style="padding: 6px 0;"><strong>🧭 Centroid:</strong></td>
										<td style="padding: 6px 0; text-align: right; font-size: 10px;">${centerLat.toFixed(5)}, ${centerLng.toFixed(5)}</td>
									</tr>
									<tr>
										<td style="padding: 6px 0;"><strong>👨‍🌾 Owner:</strong></td>
										<td style="padding: 6px 0; text-align: right;">${frm.doc.outgrower || 'N/A'}</td>
									</tr>
								</table>
							</div>
						`, {
							maxWidth: 300
						}).openPopup();
					}

					// Fit map to polygon bounds with padding
					map.fitBounds(polygon.getBounds(), { padding: [80, 80] });

					// Add measurement lines between vertices
					for (let i = 0; i < coordinates.length; i++) {
						let start = coordinates[i];
						let end = coordinates[(i + 1) % coordinates.length];

						// Calculate distance
						let distance = map.distance(start, end);
						let midPoint = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2];

						// Add distance label
						let distanceLabel = L.divIcon({
							className: 'distance-label',
							html: `<div style="background: rgba(255, 255, 255, 0.9); color: #666; padding: 4px 8px; border-radius: 3px; font-size: 10px; border: 1px solid #ddd; white-space: nowrap;">
								${distance.toFixed(1)} m
							</div>`,
							iconSize: [60, 20],
							iconAnchor: [30, 10]
						});
						L.marker(midPoint, { icon: distanceLabel }).addTo(map);
					}

					// Force map to resize/refresh
					setTimeout(function() {
						map.invalidateSize();
					}, 100);

					// Add custom CSS for animations
					let style = document.createElement('style');
					style.innerHTML = `
						.plot-polygon {
							transition: all 0.3s ease;
						}
						.plot-polygon:hover {
							fill-opacity: 0.4 !important;
						}
						.leaflet-popup-content {
							margin: 15px;
						}
						.leaflet-popup-content h4 {
							font-weight: 600;
						}
					`;
					document.head.appendChild(style);

				} catch (error) {
					console.error('Error rendering map:', error);
					frappe.msgprint({
						title: __('Map Error'),
						message: __('Could not render map. Error: {0}', [error.message]),
						indicator: 'red'
					});
				}
			}, 300);
		}
	}, 100);
}
