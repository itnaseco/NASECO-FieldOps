// Copyright (c) 2026, NASECO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Outgrower Production Contract', {
	setup(frm) {
		frm.set_query('farm_plot', () => ({
			filters: { outgrower: frm.doc.outgrower, status: 'Active' }
		}));
		frm.set_query('variety', () => ({
			filters: { crop: frm.doc.crop }
		}));
		frm.set_query('crop_recipe', () => ({
			filters: { crop: frm.doc.crop }
		}));
		frm.set_query('season', () => {
			const referenceDate = frm.doc.planting_start_date || frappe.datetime.get_today();
			return {
				filters: {
					start_date: ['<=', referenceDate],
					end_date: ['>=', referenceDate]
				}
			};
		});
		frm.set_query('contract_template', () => ({
			filters: {
				docstatus: 1,
				status: 'Active',
				season: frm.doc.season,
				crop: frm.doc.crop,
				production_category: frm.doc.production_category,
				seed_class: frm.doc.seed_class
			}
		}));
		frm.set_query('pricing_policy', () => ({
			filters: {
				docstatus: 1,
				status: 'Active',
				season: frm.doc.season,
				crop: frm.doc.crop,
				production_category: frm.doc.production_category,
				seed_class: frm.doc.seed_class
			}
		}));
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.season) {
			set_season_for_date(frm, frappe.datetime.get_today());
		}
	},

	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.contract_template) {
			frm.add_custom_button(__('Open Contract Template'), () => {
				frappe.set_route('Form', 'Production Contract Template', frm.doc.contract_template);
			}, __('Navigate'));
		}
		if (frm.doc.pricing_policy) {
			frm.add_custom_button(__('Open Pricing Policy'), () => {
				frappe.set_route('Form', 'Outgrower Pricing Policy', frm.doc.pricing_policy);
			}, __('Navigate'));
		}
		if (frm.doc.linked_crop_cycle) {
			frm.add_custom_button(__('View Production Lots'), () => {
				frappe.set_route('List', 'Crop Production Lot', {
					crop_cycle: frm.doc.linked_crop_cycle
				});
			}, __('Navigate'));
		}

		if (!frm.doc.supplier && frm.doc.outgrower && frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Create Outgrower Supplier'), () => {
				frappe.call({
					method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_production_contract.outgrower_production_contract.ensure_supplier',
					args: { outgrower: frm.doc.outgrower },
					freeze: true,
					callback() {
						frm.reload_doc();
					}
				});
			}, __('Actions'));
		}

		if (frm.doc.docstatus === 1 && frm.doc.status === 'Active') {
			frm.add_custom_button(
				frm.doc.linked_crop_cycle ? __('Open Crop Cycle') : __('Create Crop Cycle'),
				() => {
					if (frm.doc.linked_crop_cycle) {
						frappe.set_route('Form', 'Crop Cycle', frm.doc.linked_crop_cycle);
						return;
					}
					frappe.call({
						method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_production_contract.outgrower_production_contract.create_crop_cycle',
						args: { production_contract: frm.doc.name },
						freeze: true,
						callback(r) {
							if (r.message) frappe.set_route('Form', 'Crop Cycle', r.message);
						}
					});
				},
				__('Actions')
			);

			frm.add_custom_button(
				frm.doc.erpnext_contract ? __('Open Supplier Contract') : __('Create Supplier Contract'),
				() => {
					if (frm.doc.erpnext_contract) {
						frappe.set_route('Form', 'Contract', frm.doc.erpnext_contract);
						return;
					}
					frappe.call({
						method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_production_contract.outgrower_production_contract.create_erpnext_contract',
						args: { production_contract: frm.doc.name },
						freeze: true,
						callback(r) {
							if (r.message) frappe.set_route('Form', 'Contract', r.message);
						}
					});
				},
				__('Contracts')
			);
		}
	},

	outgrower(frm) {
		set_supplier_from_outgrower(frm);
	},

	farm_plot(frm) {
		if (!frm.doc.farm_plot) return;

		frappe.db.get_value('Farm Plot', frm.doc.farm_plot, 'outgrower').then((r) => {
			const outgrower = r.message?.outgrower;
			if (outgrower && outgrower !== frm.doc.outgrower) {
				return frm.set_value('outgrower', outgrower);
			}
			if (outgrower) return set_supplier_from_outgrower(frm);
		});
	},

	planting_start_date(frm) {
		set_season_for_date(frm, frm.doc.planting_start_date);
	},

	contract_template(frm) {
		if (!frm.doc.contract_template) return;
		return frappe.db.get_doc('Production Contract Template', frm.doc.contract_template)
			.then((template) => {
				return frappe.run_serially([
					() => frm.set_value('pricing_policy', template.pricing_policy),
					() => frm.set_value('template_version', template.template_version),
					() => frm.set_value('agreement_title', template.agreement_title),
					() => frm.set_value('seed_handbook_reference', template.seed_handbook_reference),
					() => frm.set_value('legal_reference', template.legal_reference),
					() => frm.set_value('company_obligations', template.company_responsibilities),
					() => frm.set_value('farmer_obligations', template.farmer_responsibilities),
					() => frm.set_value('supervisor_obligations', template.supervisor_responsibilities),
					() => frm.set_value('quality_standard_terms', template.quality_terms),
					() => frm.set_value('input_recovery_terms', template.input_recovery_terms),
					() => frm.set_value('termination_terms', template.termination_terms)
				]);
			});
	},

	pricing_policy(frm) {
		if (!frm.doc.pricing_policy) return;
		return frappe.db.get_doc('Outgrower Pricing Policy', frm.doc.pricing_policy)
			.then((policy) => frappe.run_serially([
				() => frm.set_value('pricing_policy_version', policy.policy_version),
				() => frm.set_value('quota_kg_per_acre', policy.quota_kg_per_acre),
				() => frm.set_value('contract_rate', policy.advance_valuation_rate),
				() => frm.set_value('currency', policy.currency)
			]));
	},

	contracted_area_acres: calculate_contract_values,
	quota_kg_per_acre: calculate_contract_values,
	expected_yield_qty: calculate_expected_value,
	contract_rate: calculate_contract_values,
	planned_parent_seed_qty: calculate_contract_values,
	parent_seed_rate: calculate_contract_values
});

function set_season_for_date(frm, referenceDate) {
	if (!referenceDate) {
		return frm.set_value('season', null);
	}

	return frappe.call({
		method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season.get_season_for_date',
		args: { reference_date: referenceDate }
	}).then((r) => {
		return frm.set_value('season', r.message?.name || null);
	});
}

function set_supplier_from_outgrower(frm) {
	if (!frm.doc.outgrower) {
		return frm.set_value('supplier', null);
	}

	return frappe.db.get_value('Outgrower', frm.doc.outgrower, 'supplier').then((r) => {
		return frm.set_value('supplier', r.message?.supplier || null);
	});
}

function calculate_expected_value(frm) {
	frm.set_value(
		'expected_harvest_value',
		flt(frm.doc.expected_yield_qty) * flt(frm.doc.contract_rate)
	);
}

function calculate_contract_values(frm) {
	frm.set_value(
		'contracted_quota_qty',
		flt(frm.doc.contracted_area_acres) * flt(frm.doc.quota_kg_per_acre)
	);
	frm.set_value(
		'planned_parent_seed_value',
		flt(frm.doc.planned_parent_seed_qty) * flt(frm.doc.parent_seed_rate)
	);
	calculate_expected_value(frm);
}

// Seed classification master filters.
frappe.ui.form.on("Outgrower Production Contract", {
	setup(frm) {
		frm.set_query("production_category", () => ({ filters: { enabled: 1 } }));
		frm.set_query("seed_class", () => ({ filters: { enabled: 1 } }));
	}
});
