// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.listview_settings['Farm Plot'] = {
	add_fields: ['centroid_lat', 'centroid_lng'],
	button: {
		show(doc) {
			return !!(doc.centroid_lat && doc.centroid_lng);
		},
		get_label() {
			return frappe.utils.icon('es-line-location', 'sm');
		},
		get_description(doc) {
			return __('View {0} on the map', [doc.plot_id || doc.name]);
		},
		action(doc) {
			frappe.call({
				method: 'frappe.client.get',
				args: { doctype: 'Farm Plot', name: doc.name },
				freeze: true,
				callback(r) {
					if (!r.message) return;
					frappe.require('/assets/naseco_fieldopsbackend/js/plot_map_dialog.js').then(() => {
						naseco_fieldopsbackend.show_plot_map_dialog(r.message);
					});
				}
			});
		}
	}
};
