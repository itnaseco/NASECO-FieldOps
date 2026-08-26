// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

frappe.ui.form.on("Outgrower", {
	setup(frm) {
		frm.set_query('assigned_supervisor', () => ({
			query: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower.outgrower.outgrower_supervisor_query'
		}));
		frm.set_query('default_bank_account', () => ({
			filters: {
				party_type: 'Supplier',
				party: frm.doc.supplier,
				disabled: 0
			}
		}));
	},

	refresh(frm) {
		// Add custom button to create new plot for this outgrower
		if (!frm.is_new()) {
			if (!frm.doc.supplier) {
				frm.add_custom_button(__('Create Supplier'), function() {
					frappe.call({
						method: 'naseco_fieldopsbackend.fieldops_finance.ensure_outgrower_supplier',
						args: { outgrower: frm.doc.name },
						freeze: true,
						freeze_message: __('Creating Supplier...'),
						callback(r) {
							if (r.message) {
								frappe.show_alert({
									message: __('Supplier {0} created', [r.message]),
									indicator: 'green'
								});
								frm.reload_doc();
							}
						}
					});
				}, __('Actions'));
			} else {
				frm.add_custom_button(__('Open Supplier'), function() {
					frappe.set_route('Form', 'Supplier', frm.doc.supplier);
				}, __('Navigate'));

				if (frm.doc.default_bank_account) {
					frm.add_custom_button(__('Open Bank Account'), function() {
						frappe.set_route('Form', 'Bank Account', frm.doc.default_bank_account);
					}, __('Navigate'));
				} else {
					frm.add_custom_button(__('Create Bank Account'), function() {
						frappe.new_doc('Bank Account', {
							account_name: frm.doc.full_name,
							party_type: 'Supplier',
							party: frm.doc.supplier
						});
					}, __('Actions'));
				}
			}

			frm.add_custom_button(__('Create New Plot'), function() {
				frappe.new_doc('Farm Plot', {
					outgrower: frm.doc.name
				});
			}, __('Actions'));

			frm.add_custom_button(__('New Production Contract'), function() {
				frappe.new_doc('Outgrower Production Contract', {
					outgrower: frm.doc.name,
					supplier: frm.doc.supplier
				});
			}, __('Actions'));

			add_related_outgrower_buttons(frm);

			// Display list of plots for this outgrower
			render_plots_section(frm);
		}
	}
});

function add_related_outgrower_buttons(frm) {
	const relations = [
		['Outgrower Production Contract', __('View Production Contracts'), 'Navigate'],
		['Inspection', __('View Inspections'), 'Actions'],
		['Field Corrective Action', __('View Corrective Actions'), 'Actions'],
		['Crop Cycle Advance Request', __('View Advance Requests'), 'Navigate'],
		['Crop Cycle Settlement', __('View Settlements'), 'Navigate']
	];
	relations.forEach(([doctype, label, group]) => {
		frappe.db.count(doctype, { filters: { outgrower: frm.doc.name } }).then((count) => {
			if (!count) return;
			frm.add_custom_button(__('{0} ({1})', [label, count]), () => {
				frappe.set_route('List', doctype, { outgrower: frm.doc.name });
			}, __(group));
		});
	});
}

function render_plots_section(frm) {
	const wrapper = get_plots_wrapper(frm);
	wrapper.empty();

	// Fetch plots for this outgrower
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'Farm Plot',
			filters: {
				outgrower: frm.doc.name
			},
			fields: ['name', 'plot_id', 'plot_name', 'plot_type', 'area_acres', 'centroid_lat', 'centroid_lng'],
			order_by: 'creation desc'
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				display_plots(frm, r.message);
			} else {
				display_empty_state(frm);
			}
		}
	});
}

function display_plots(frm, plots) {
	// Create HTML for plots list
	let html = `
		<div class="plots-section" style="margin-top: 15px; padding: 15px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb;">
			<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
				<h4 style="margin: 0; color: #1f2937; font-size: 16px; font-weight: 600;">
					<svg style="width: 18px; height: 18px; display: inline-block; vertical-align: middle; margin-right: 8px;" fill="currentColor" viewBox="0 0 20 20">
						<path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"></path>
					</svg>
					Farm Plots (${plots.length})
				</h4>
				<span style="color: #6b7280; font-size: 13px;">Click to view details</span>
			</div>
			<div class="plots-list">
	`;

	plots.forEach(function(plot) {
		let area_display = plot.area_acres ? `${plot.area_acres} acres` : 'Not calculated';
		let location_display = (plot.centroid_lat && plot.centroid_lng)
			? `${plot.centroid_lat.toFixed(4)}, ${plot.centroid_lng.toFixed(4)}`
			: 'No GPS data';

		// Determine plot type color
		let type_color = plot.plot_type === 'Owned' ? '#10b981' :
						 plot.plot_type === 'Leased' ? '#f59e0b' : '#6b7280';

		html += `
			<div class="plot-item" data-plot-name="${plot.name}" style="
				background: white;
				border: 1px solid #e5e7eb;
				border-radius: 6px;
				padding: 12px;
				margin-bottom: 10px;
				cursor: pointer;
				transition: all 0.2s ease;
				box-shadow: 0 1px 2px rgba(0,0,0,0.05);
			" onmouseover="this.style.boxShadow='0 4px 6px rgba(0,0,0,0.1)'; this.style.borderColor='#3b82f6'; this.style.transform='translateY(-2px)';"
			   onmouseout="this.style.boxShadow='0 1px 2px rgba(0,0,0,0.05)'; this.style.borderColor='#e5e7eb'; this.style.transform='translateY(0)';">

				<div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
					<div>
						<div style="font-weight: 600; color: #1f2937; font-size: 14px; margin-bottom: 4px;">
							${plot.plot_name || plot.plot_id}
						</div>
						<div style="color: #6b7280; font-size: 12px;">
							ID: ${plot.plot_id}
						</div>
					</div>
					<span style="
						background: ${type_color};
						color: white;
						padding: 3px 10px;
						border-radius: 12px;
						font-size: 11px;
						font-weight: 500;
					">${plot.plot_type || 'N/A'}</span>
				</div>

				<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px;">
					<div style="background: #f3f4f6; padding: 6px 10px; border-radius: 4px;">
						<div style="color: #6b7280; font-size: 11px; margin-bottom: 2px;">Area</div>
						<div style="color: #1f2937; font-size: 13px; font-weight: 500;">${area_display}</div>
					</div>
					<div style="background: #f3f4f6; padding: 6px 10px; border-radius: 4px;">
						<div style="color: #6b7280; font-size: 11px; margin-bottom: 2px;">GPS Center</div>
						<div style="color: #1f2937; font-size: 11px; font-weight: 500;">${location_display}</div>
					</div>
				</div>

				<div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #e5e7eb;">
					<span style="color: #3b82f6; font-size: 12px; font-weight: 500;">
						View Details →
					</span>
				</div>
			</div>
		`;
	});

	html += `
			</div>
		</div>
	`;

	const wrapper = get_plots_wrapper(frm);
	wrapper.empty();
	$(html).appendTo(wrapper);

	// Add click handlers
	wrapper.find('.plot-item').on('click', function() {
		let plot_name = $(this).data('plot-name');
		frappe.set_route('Form', 'Farm Plot', plot_name);
	});
}

function display_empty_state(frm) {
	// Display empty state when no plots exist
	let html = `
		<div class="plots-section" style="margin-top: 15px; padding: 30px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb; text-align: center;">
			<svg style="width: 48px; height: 48px; margin: 0 auto 15px; color: #9ca3af;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
			</svg>
			<h4 style="margin: 10px 0; color: #4b5563; font-size: 15px;">No Farm Plots Yet</h4>
			<p style="color: #6b7280; font-size: 13px; margin: 10px 0 20px;">
				This outgrower doesn't have any farm plots registered. Click the button below to create the first plot.
			</p>
			<button class="btn btn-primary btn-sm create-first-plot" style="padding: 8px 20px;">
				<svg style="width: 16px; height: 16px; display: inline-block; vertical-align: middle; margin-right: 5px;" fill="currentColor" viewBox="0 0 20 20">
					<path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd"></path>
				</svg>
				Create First Plot
			</button>
		</div>
	`;

	const wrapper = get_plots_wrapper(frm);
	wrapper.empty();
	$(html).appendTo(wrapper);

	// Add click handler for create button
	wrapper.find('.create-first-plot').on('click', function() {
		frappe.new_doc('Farm Plot', {
			outgrower: frm.doc.name
		});
	});
}

function get_plots_wrapper(frm) {
	if (frm.fields_dict.farm_plots_html && frm.fields_dict.farm_plots_html.$wrapper) {
		return frm.fields_dict.farm_plots_html.$wrapper;
	}
	// Fallback for older schema not yet migrated
	return frm.fields_dict.status.$wrapper.parent();
}
