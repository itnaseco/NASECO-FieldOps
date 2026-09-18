// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.provide('naseco_fieldopsbackend');

// Shared "View on Map" dialog for a Farm Plot. Accepts a plain plot object
// (a Farm Plot doc, or an frm.doc) carrying: polygon (Plot Vertex rows),
// area_hectares, perimeter_meters, centroid_lat, centroid_lng, plot_name,
// plot_id, outgrower. Used by both the Farm Plot form and the Farm Plot list view.
naseco_fieldopsbackend.show_plot_map_dialog = function (plot) {
	let vertices = plot.polygon || [];

	if (vertices.length < 3) {
		frappe.msgprint(__('Plot must have at least 3 vertices to display on map'));
		return;
	}

	vertices = [...vertices].sort((a, b) => a.order_index - b.order_index);
	let coordinates = vertices.map(v => [parseFloat(v.latitude), parseFloat(v.longitude)]);

	let centerLat = plot.centroid_lat || coordinates[0][0];
	let centerLng = plot.centroid_lng || coordinates[0][1];

	const map_id = "plot_map_container_" + Date.now() + "_" + Math.random().toString(36).slice(2);
	let rendered_map = null;
	let dialog_closed = false;

	let d = new frappe.ui.Dialog({
		title: __('Plot Map: {0}', [plot.plot_name || plot.plot_id || plot.name]),
		size: 'extra-large',
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'map_html'
			}
		]
	});

	d.$wrapper.one("hidden.bs.modal", () => {
		dialog_closed = true;
		if (rendered_map) {
			rendered_map.remove();
			rendered_map = null;
		}
	});

	d.show();
	d.$wrapper.find('.modal-dialog .modal-content').addClass('plot-map-modal-modern');

	setTimeout(function () {
		let map_container = `
			<div style="position: relative;">
				<div id="${map_id}" style="height: 700px; width: 100%; border: 1px solid #ddd; border-radius: 8px;"></div>
				<div class="plot-map-legend" id="plot_map_legend" style="position: absolute; bottom: 20px; left: 20px; background: var(--card-bg, #fff); border-radius: 10px; box-shadow: 0 6px 24px rgba(0,0,0,0.18); z-index: 1000; max-width: 260px; overflow: hidden;">
					<div class="plot-map-legend-header" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 15px; cursor: pointer; user-select: none;">
						<h5 style="margin: 0; font-size: 14px; font-weight: bold;">📍 ${__('Map Legend')}</h5>
						<span class="plot-map-legend-toggle" style="transition: transform 0.2s ease; font-size: 12px;">▾</span>
					</div>
					<div class="plot-map-legend-body" style="padding: 0 15px 15px; max-height: 400px; opacity: 1; transition: max-height 0.2s ease, opacity 0.2s ease, padding 0.2s ease;">
						<div style="display: flex; align-items: center; margin: 8px 0;">
							<div style="width: 20px; height: 3px; background: #2563eb; margin-right: 10px;"></div>
							<span style="font-size: 12px;">${__('Plot Boundary')}</span>
						</div>
						<div style="display: flex; align-items: center; margin: 8px 0;">
							<div style="width: 16px; height: 20px; background: #dc3545; clip-path: polygon(50% 0%, 100% 100%, 0% 100%); margin-right: 10px;"></div>
							<span style="font-size: 12px;">${__('Centroid')}</span>
						</div>
						<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee;">
							<div style="font-size: 11px; color: #666;">
								<strong>${__('Area')}:</strong> ${(plot.area_hectares || 0).toFixed(3)} ${__('hectares')}<br>
								<strong>${__('Perimeter')}:</strong> ${(plot.perimeter_meters || 0).toFixed(1)} m
							</div>
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

		if (!document.getElementById('leaflet-css')) {
			let link = document.createElement('link');
			link.id = 'leaflet-css';
			link.rel = 'stylesheet';
			link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
			document.head.appendChild(link);
		}

		if (typeof L === 'undefined') {
			let script = document.createElement('script');
			script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
			script.onload = function () {
				render_map();
			};
			document.head.appendChild(script);
		} else {
			render_map();
		}

		function render_map() {
			setTimeout(function () {
				try {
					const map_element = d.fields_dict.map_html.$wrapper.find('#' + map_id)[0];
					if (dialog_closed || !map_element || !document.body.contains(map_element)) return;
					rendered_map = L.map(map_element, {
						zoomControl: true,
						attributionControl: true,
						maxZoom: 23,
						zoomSnap: 0.25
					}).setView([centerLat, centerLng], 17);
					const map = rendered_map;

					let baseLayers = {
						"🛰️ Satellite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
							attribution: 'Tiles © Esri',
							maxZoom: 23
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
								maxZoom: 23
							}),
							L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}.png', {
								attribution: '© CartoDB',
								maxZoom: 19,
								pane: 'shadowPane'
							})
						])
					};

					baseLayers["🛰️ Satellite"].addTo(map);

					L.control.layers(baseLayers, null, {
						position: 'topright',
						collapsed: false
					}).addTo(map);

					L.control.scale({
						position: 'bottomright',
						imperial: false,
						metric: true
					}).addTo(map);

					let polygon = L.polygon(coordinates, {
						color: '#2563eb',
						fillColor: '#2563eb',
						fillOpacity: 0.12,
						weight: 4,
						className: 'plot-polygon'
					}).addTo(map);

					let polygonCenter = polygon.getBounds().getCenter();
					let areaLabel = L.divIcon({
						className: 'area-label',
						html: `<div style="background: rgba(37, 99, 235, 0.92); color: white; padding: 8px 12px; border-radius: 6px; font-size: 13px; font-weight: bold; white-space: nowrap; box-shadow: 0 2px 8px rgba(0,0,0,0.3);">
							${(plot.area_hectares || 0).toFixed(3)} hectares
						</div>`,
						iconSize: [100, 30],
						iconAnchor: [50, 15]
					});
					L.marker(polygonCenter, { icon: areaLabel }).addTo(map);

					if (plot.centroid_lat && plot.centroid_lng) {
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
									📍 ${plot.plot_name || plot.plot_id || ''}
								</h4>
								<table style="width: 100%; font-size: 12px; border-collapse: collapse;">
									<tr style="border-bottom: 1px solid #eee;">
										<td style="padding: 6px 0;"><strong>📐 Area:</strong></td>
										<td style="padding: 6px 0; text-align: right;">${(plot.area_hectares || 0).toFixed(3)} hectares</td>
									</tr>
									<tr style="border-bottom: 1px solid #eee;">
										<td style="padding: 6px 0;"><strong>📏 Perimeter:</strong></td>
										<td style="padding: 6px 0; text-align: right;">${(plot.perimeter_meters || 0).toFixed(1)} m</td>
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
										<td style="padding: 6px 0; text-align: right;">${plot.outgrower || 'N/A'}</td>
									</tr>
								</table>
							</div>
						`, {
							maxWidth: 300
						}).openPopup();
					}

					map.fitBounds(polygon.getBounds(), { padding: [80, 80] });

					setTimeout(function () {
						map.invalidateSize();
					}, 100);

					if (!document.getElementById('plot-map-polygon-anim-style')) {
						let style = document.createElement('style');
						style.id = 'plot-map-polygon-anim-style';
						style.innerHTML = `
							.plot-polygon { transition: all 0.3s ease; }
							.plot-polygon:hover { fill-opacity: 0.4 !important; }
							.leaflet-popup-content { margin: 15px; }
							.leaflet-popup-content h4 { font-weight: 600; }
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
			}, 300);
		}
	}, 100);
};
