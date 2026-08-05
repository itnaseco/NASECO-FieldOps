frappe.ui.form.on("Stage Input Dispatch", {
	setup(frm) {
		frm.set_query("stock_entry", () => ({
			filters: {
				docstatus: 1,
				custom_stage_input_request: ["is", "set"],
			},
		}));
	},

	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Open Stock Entry"), () => {
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
			});
			frm.add_custom_button(__("Open Input Request"), () => {
				frappe.set_route("Form", "Stage Input Request", frm.doc.input_request);
			});
		}
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Capture Delivery Location"), () => {
				capture_delivery_location(frm);
			}, __("Actions"));
		}
	},

	stock_entry(frm) {
		if (!frm.doc.stock_entry) {
			return;
		}
		frappe.call({
			method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.stage_input_dispatch.stage_input_dispatch.get_unacknowledged_stock_rows",
			args: { stock_entry: frm.doc.stock_entry },
			callback: ({ message: rows }) => {
				if (!rows?.length) {
					frappe.msgprint(__("This Stock Entry has no unacknowledged FieldOps input rows."));
					return;
				}
				const options = rows.map((row) => row.name);
				const description = rows
					.map((row) => `${row.name}: ${row.item_code} - ${row.transfer_qty} ${row.stock_uom}`)
					.join("<br>");
				const dialog = new frappe.ui.Dialog({
					title: __("Select Issued Input"),
					fields: [{
						fieldname: "stock_entry_detail",
						fieldtype: "Select",
						label: __("Stock Entry Item"),
						options,
						description,
						reqd: 1,
					}],
					primary_action_label: __("Select"),
					primary_action(values) {
						frm.set_value("stock_entry_detail", values.stock_entry_detail);
						dialog.hide();
						frappe.call({
							method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.stage_input_dispatch.stage_input_dispatch.get_stock_row_context",
							args: { stock_entry_detail: values.stock_entry_detail },
							callback: ({ message }) => {
								Object.entries(message || {}).forEach(([fieldname, value]) => {
									frm.set_value(fieldname, value);
								});
							},
						});
					},
				});
				dialog.show();
			},
		});
	},
});

function capture_delivery_location(frm) {
	if (!navigator.geolocation) {
		frappe.msgprint(__("Geolocation is not available on this device."));
		return;
	}
	frappe.dom.freeze(__("Capturing an accurate delivery location..."));
	navigator.geolocation.getCurrentPosition(
		(position) => {
			const { latitude, longitude, accuracy } = position.coords;
			frm.set_value("geolocation", JSON.stringify({
				type: "FeatureCollection",
				features: [{
					type: "Feature",
					properties: {},
					geometry: { type: "Point", coordinates: [longitude, latitude] },
				}],
			}));
			frm.set_value("gps_accuracy_meters", accuracy);
			frappe.db.get_single_value("FieldOps Settings", "preferred_gps_accuracy_m")
				.then((preferred) => {
					const quality = accuracy <= flt(preferred || 10)
						? "Good"
						: accuracy <= flt(preferred || 10) * 2 ? "Marginal" : "Poor";
					frm.set_value("gps_quality_status", quality);
				});
			frappe.dom.unfreeze();
		},
		(error) => {
			frappe.dom.unfreeze();
			frappe.msgprint(__("Could not capture the delivery location: {0}", [error.message]));
		},
		{ enableHighAccuracy: true, timeout: 30000, maximumAge: 0 }
	);
}
