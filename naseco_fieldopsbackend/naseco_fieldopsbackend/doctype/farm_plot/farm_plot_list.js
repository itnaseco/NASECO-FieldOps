// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.listview_settings['Farm Plot'] = {
	add_fields: ['centroid_lat', 'centroid_lng'],
	button: {
		show(doc) {
			return !!(doc.centroid_lat && doc.centroid_lng);
		},
		get_label() {
			return `${frappe.utils.icon('es-line-location', 'xs')} <span style="margin-left: 4px;">${__('View Map')}</span>`;
		},
		get_description(doc) {
			return __('View {0} on the map', [doc.plot_id || doc.name]);
		},
		action(doc) {
			// frappe.model.with_doc caches the fetched doc, so reopening the
			// same plot's map is instant on subsequent clicks.
			Promise.all([
				frappe.model.with_doc('Farm Plot', doc.name),
				frappe.require('/assets/naseco_fieldopsbackend/js/plot_map_dialog.js')
			]).then(([plot_doc]) => {
				if (plot_doc) naseco_fieldopsbackend.show_plot_map_dialog(plot_doc);
			});
		}
	}
};
