frappe.ui.form.on("Crop Cycle Settlement", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Open Crop Cycle"), () => {
			frappe.set_route("Form", "Crop Cycle", frm.doc.crop_cycle);
		});

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Refresh Source Vouchers"), () => {
				frappe.call({
					method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_settlement.crop_cycle_settlement.refresh_settlement",
					args: { settlement: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			}, __("Actions"));
		}

		if (frm.doc.purchase_invoice) {
			frm.add_custom_button(__("Open Purchase Invoice"), () => {
				frappe.set_route("Form", "Purchase Invoice", frm.doc.purchase_invoice);
			}, __("Actions"));
		}

		if (frm.doc.docstatus === 1 && frm.doc.purchase_invoice) {
			frappe.db.get_value("Purchase Invoice", frm.doc.purchase_invoice, ["docstatus", "outstanding_amount"])
				.then(({ message }) => {
					if (message.docstatus === 2) {
						frm.add_custom_button(__("Create Replacement Invoice"), () => {
							frappe.call({
								method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_settlement.crop_cycle_settlement.create_purchase_invoice",
								args: { settlement: frm.doc.name },
								freeze: true,
								callback: () => frm.reload_doc(),
							});
						}, __("Actions"));
					}
					if (message.docstatus === 1 && flt(message.outstanding_amount) > 0) {
						frm.add_custom_button(__("Create Net Payment"), () => {
							frappe.call({
								method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_cycle_settlement.crop_cycle_settlement.create_net_payment",
								args: { settlement: frm.doc.name },
								freeze: true,
								callback: ({ message: payment_entry }) => {
									if (payment_entry) {
										frappe.set_route("Form", "Payment Entry", payment_entry);
									}
								},
							});
						}, __("Actions"));
					}
				});
		}

		frm.dashboard.add_indicator(
			__("Gross harvest: {0}", [format_currency(frm.doc.gross_harvest_value, frm.doc.currency)]),
			"blue"
		);
		frm.dashboard.add_indicator(
			__("Recoveries: {0}", [format_currency(
				flt(frm.doc.stock_recovery_to_deduct) + flt(frm.doc.cash_advance_to_allocate),
				frm.doc.currency
			)]),
			"orange"
		);
		frm.dashboard.add_indicator(
			__("Net payable: {0}", [format_currency(frm.doc.net_payable, frm.doc.currency)]),
			"green"
		);
		if (flt(frm.doc.unrecovered_balance) > 0) {
			frm.dashboard.add_indicator(
				__("Unrecovered: {0}", [format_currency(frm.doc.unrecovered_balance, frm.doc.currency)]),
				"red"
			);
		}
	},
});
