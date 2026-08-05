frappe.ui.form.on("Seed Harvest Quality Assessment", {
	setup(frm) {
		frm.set_query("inspected_by", () => ({
			query: "naseco_fieldopsbackend.roles.user_with_role_query",
			filters: { role: "Quality Inspector" }
		}));
		frm.set_query("verified_by", () => ({
			query: "naseco_fieldopsbackend.roles.user_with_role_query",
			filters: { role: "Quality Manager" }
		}));
		frm.set_query("production_lot", () => ({
			filters: { crop_cycle: frm.doc.crop_cycle }
		}));
		frm.set_query("purchase_receipt", () => ({
			filters: {
				docstatus: 1,
				custom_production_contract: frm.doc.production_contract
			}
		}));
		frm.set_query("quality_inspection", () => ({
			filters: {
				reference_type: "Purchase Receipt",
				reference_name: frm.doc.purchase_receipt,
				item_code: frm.doc.item_code
			}
		}));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		if (!frm.doc.quality_inspection && frm.doc.docstatus === 0 && frm.doc.purchase_receipt_item) {
			frm.add_custom_button(__("Create Quality Inspection"), () => {
				frappe.call({
					method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.seed_harvest_quality_assessment.seed_harvest_quality_assessment.create_quality_inspection",
					args: { assessment: frm.doc.name },
					freeze: true,
					callback(r) {
						if (r.message) {
							frappe.set_route("Form", "Quality Inspection", r.message);
						}
					}
				});
			}, __("Actions"));
		}
		if (frm.doc.quality_inspection) {
			frm.add_custom_button(__("Open Quality Inspection"), () => {
				frappe.set_route("Form", "Quality Inspection", frm.doc.quality_inspection);
			}, __("Navigate"));
		}
		frm.add_custom_button(__("Open Production Lot"), () => {
			frappe.set_route("Form", "Crop Production Lot", frm.doc.production_lot);
		}, __("Navigate"));
	}
});
