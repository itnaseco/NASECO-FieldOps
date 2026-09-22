// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.provide('naseco_fieldopsbackend');

// Shared "View on Map" dialog for a Farm Plot. Keep the polygon itself clear:
// plot metadata belongs in the collapsible legend, not over small parcels.
naseco_fieldopsbackend.show_plot_map_dialog = function (plot) {
	let vertices = plot.polygon || [];

	if (vertices.length < 3) {
		frappe.msgprint(__('Plot must have at least 3 vertices to display on map'));
		return;
	}

	vertices = [...vertices].sort((a, b) => a.order_index - b.order_index);
	let coordinates = vertices.map(v => [parseFloat(v.latitude), parseFloat(v.longitude)]);
	let centerLat = parseFloat(plot.centroid_lat) || coordinates[0][0];
	let centerLng = parseFloat(plot.centroid_lng) || coordinates[0][1];
	const area = Number(plot.area_hectares) || 0;
	const perimeter = Number(plot.perimeter_meters) || 0;
	const plot_label = plot.plot_name || plot.plot_id || plot.name || '';
	const owner = plot.outgrower || __('Not available');

	const map_id = "plot_map_container_" + Date.now() + "_" + Math.random().toString(36).slice(2);
	let rendered_map = null;
	let dialog_closed = false;

	let d = new frappe.ui.Dialog({
		title: __('Plot Map: {0}', [plot_label]),
		size: 'extra-large',
		fields: [{ fieldtype: 'HTML', fieldname: 'map_html' }]
	});

	d.$wrapper.one("hidden.bs.modal", () => {
		dialog_closed = true;
		if (rendered_map) {
			rendered_map.remove();
			rendered_map = null;
		}
	});

	let map_container = `
		<div style="position: relative;">
			<div id="${map_id}" style="height: 700px; width: 100%; border: 1px solid #ddd; border-radius: 8px; position: relative;">
				<div class="plot-map-loading" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: #eef1f4; color: #8896a6; font-size: 13px; border-radius: 8px;">
					${__('Loading map...')}
				</div>
			</div>
			<div class="plot-map-legend" style="position: absolute; bottom: 20px; left: 20px; background: var(--card-bg, #fff); border-radius: 10px; box-shadow: 0 6px 24px rgba(0,0,0,0.18); z-index: 1000; max-width: 290px; overflow: hidden;">
				<div class="plot-map-legend-header" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 15px; cursor: pointer; user-select: none;">
					<h5 style="margin: 0; font-size: 14px; font-weight: bold;">${__('Map Legend')}</h5>
					<span class="plot-map-legend-toggle" style="transition: transform 0.2s ease; font-size: 12px;">▾</span>
				</div>
				<div class="plot-map-legend-body" style="padding: 0 15px 15px; max-height: 400px; opacity: 1; transition: max-height 0.2s ease, opacity 0.2s ease, padding 0.2s ease;">
					<div style="display: flex; align-items: center; margin: 8px 0 12px;">
						<div style="width: 20px; height: 3px; background: #2563eb; margin-right: 10px;"></div>
						<span style="font-size: 12px;">${__('Plot Boundary')}</span>
					</div>
					<div style="padding-top: 10px; border-top: 1px solid #eee; font-size: 11px; color: var(--text-muted, #666); line-height: 1.7;">
						<div><strong>${__('Plot')}:</strong> ${frappe.utils.escape_html(plot_label)}</div>
						<div><strong>${__('Area')}:</strong> ${area.toFixed(3)} ${__('hectares')}</div>
						<div><strong>${__('Perimeter')}:</strong> ${perimeter.toFixed(1)} m</div>
						<div><strong>${__('Vertices')}:</strong> ${coordinates.length}</div>
						<div><strong>${__('Location')}:</strong> ${centerLat.toFixed(6)}, ${centerLng.toFixed(6)}</div>
						<div><strong>${__('Owner')}:</strong> ${frappe.utils.escape_html(String(owner))}</div>
					</div>
				</div>
			</div>
		</div>
		<style>
			.leaflet-container { height: 100%; width: 100%; }
			.leaflet-control-layers { border: 2px solid rgba(0,0,0,0.2); border-radius: 8px; }
			.plot-map-modal-modern .modal-content { border-radius: 12px; overflow: hidden; }
			.plot-map-legend.collapsed .plot-map-legend-body {
				max-height: 0 !important;
				opacity: 0 !important;
				padding-top: 0 !important;
				padding-bottom: 0 !important;
			}
			.plot-map-legend.collapsed .plot-map-legend-toggle { transform: rotate(-90deg); }
		</style>
	`;

	d.fields_dict.map_html.$wrapper.html(map_container);
	d.fields_dict.map_html.$wrapper.find('.plot-map-legend-header').on('click', function () {
		d.fields_dict.map_html.$wrapper.find('.plot-map-legend').toggleClass('collapsed');
	});

	const shown = new Promise((resolve) => d.$wrapper.one('shown.bs.modal', resolve));
	const leaflet_ready = load_leaflet();
	d.show();
	d.$wrapper.find('.modal-dialog .modal-content').addClass('plot-map-modal-modern');
	Promise.all([shown, leaflet_ready]).then(render_map);

	function load_leaflet() {
		if (!document.getElementById('leaflet-css')) {
			let link = document.createElement('link');
			link.id = 'leaflet-css';
			link.rel = 'stylesheet';
			link.href = '/assets/frappe/js/lib/leaflet/leaflet.css';
			document.head.appendChild(link);
		}
		if (typeof L !== 'undefined') return Promise.resolve();
		return frappe.require('/assets/frappe/js/lib/leaflet/leaflet.js');
	}

	function render_map() {
		try {
			const map_element = d.fields_dict.map_html.$wrapper.find('#' + map_id)[0];
			if (dialog_closed || !map_element || !document.body.contains(map_element)) return;
			map_element.querySelector('.plot-map-loading')?.remove();

			rendered_map = L.map(map_element, {
				zoomControl: true,
				attributionControl: true,
				minZoom: 2,
				maxZoom: 23,
				zoomSnap: 0.25,
				zoomDelta: 0.5
			}).setView([centerLat, centerLng], 17);
			const map = rendered_map;

			// Satellite tiles are commonly native through z19. Leaflet may safely
			// over-zoom that imagery to z23, which provides a sub-5 m viewport for
			// inspecting very small plots without requesting nonexistent tiles.
			const satellite_options = {
				attribution: 'Tiles © Esri',
				maxNativeZoom: 19,
				maxZoom: 23
			};
			let baseLayers = {
				"Satellite": L.tileLayer(
					'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
					satellite_options
				),
				"Street Map": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
					attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
					maxNativeZoom: 19,
					maxZoom: 23
				}),
				"Terrain": L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
					attribution: '© <a href="https://opentopomap.org">OpenTopoMap</a>',
					maxNativeZoom: 17,
					maxZoom: 23
				}),
				"Hybrid": L.layerGroup([
					L.tileLayer(
						'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
						satellite_options
					),
					L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}.png', {
						attribution: '© CartoDB',
						maxNativeZoom: 19,
						maxZoom: 23,
						pane: 'shadowPane'
					})
				])
			};

			baseLayers.Satellite.addTo(map);
			L.control.layers(baseLayers, null, { position: 'topright', collapsed: false }).addTo(map);
			L.control.scale({ position: 'bottomright', imperial: false, metric: true }).addTo(map);

			const polygon = L.polygon(coordinates, {
				color: '#2563eb',
				fillColor: '#2563eb',
				fillOpacity: 0.12,
				weight: 4,
				className: 'plot-polygon'
			}).addTo(map);

			map.fitBounds(polygon.getBounds(), { padding: [50, 50], maxZoom: 21 });
			setTimeout(() => map.invalidateSize(), 100);

			if (!document.getElementById('plot-map-polygon-anim-style')) {
				let style = document.createElement('style');
				style.id = 'plot-map-polygon-anim-style';
				style.innerHTML = `
					.plot-polygon { transition: all 0.3s ease; }
					.plot-polygon:hover { fill-opacity: 0.3 !important; }
				`;
				document.head.appendChild(style);
			}
		} catch (error) {
			console.error('Error rendering map:', error);
			frappe.msgprint({
				title: __('Map Error'),
				message: __('Could not render map. Error: {0}', [error.message]),
				indicator: 'red'
			});
		}
	}
};
