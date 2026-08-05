frappe.ui.form.on("Season Production Plan", {
	setup(frm) {
		frm.set_query("outgrower_manager", () => ({
			query: "naseco_fieldopsbackend.roles.user_with_role_query",
			filters: { role: "Outgrower Manager" }
		}));
		frm.set_query("quality_manager", () => ({
			query: "naseco_fieldopsbackend.roles.user_with_role_query",
			filters: { role: "Quality Manager" }
		}));
		frm.set_query("finance_approver", () => ({
			query: "naseco_fieldopsbackend.roles.user_with_role_query",
			filters: { role: "FieldOps Finance Approver" }
		}));
		frm.set_query("stores_responsible", () => ({
			query: "naseco_fieldopsbackend.roles.user_with_role_query",
			filters: { role: "FieldOps Stores User" }
		}));
		frm.set_query("user", "resource_allocations", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				query: "naseco_fieldopsbackend.roles.user_with_role_query",
				filters: { role: row.resource_role }
			};
		});
	},

	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Open Command Centre"), () => {
			frappe.set_route("season-command-centre", { plan: frm.doc.name });
		}, __("Navigate"));

		frm.add_custom_button(__("Refresh Actuals"), () => {
			frappe.call({
				method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan.refresh_plan_actuals",
				args: { plan: frm.doc.name },
				freeze: true,
				callback: () => frm.reload_doc()
			});
		}, __("Actions"));

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Regenerate Input Requirements"), () => {
				frappe.call({
					method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan.generate_input_requirements",
					args: { plan: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc()
				});
			}, __("Actions"));
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Create Shortage Material Request"), () => {
				frappe.call({
					method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season_production_plan.season_production_plan.create_shortage_material_request",
					args: { plan: frm.doc.name },
					freeze: true,
					callback(r) {
						if (r.message) frappe.set_route("Form", "Material Request", r.message);
					}
				});
			}, __("Create"));
		}

		add_indicators(frm);
	},

	season(frm) {
		if (frm.doc.season && !frm.doc.plan_title) {
			frm.set_value("plan_title", `${frm.doc.season} Production Plan`);
		}
	}
});

frappe.ui.form.on("Season Production Target", {
	target_acres: calculate_target,
	planned_yield_kg_per_acre: calculate_target,
	planning_rate: calculate_target,
	parent_seed_rate_per_acre: calculate_target
});

function calculate_target(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "planned_production_qty",
		flt(row.target_acres) * flt(row.planned_yield_kg_per_acre));
	frappe.model.set_value(cdt, cdn, "planned_procurement_value",
		flt(row.planned_production_qty) * flt(row.planning_rate));
	frappe.model.set_value(cdt, cdn, "parent_seed_required_qty",
		flt(row.target_acres) * flt(row.parent_seed_rate_per_acre));
	frm.refresh_field("production_targets");
}

function add_indicators(frm) {
	frm.dashboard.add_indicator(
		__("Readiness: {0}%", [format_number(frm.doc.readiness_score || 0, null, 1)]),
		frm.doc.mandatory_readiness_complete ? "green" : "orange"
	);
	frm.dashboard.add_indicator(
		__("Acreage: {0}%", [format_number(frm.doc.acreage_achievement_percent || 0, null, 1)]),
		frm.doc.acreage_achievement_percent >= 100 ? "green" : "blue"
	);
	frm.dashboard.add_indicator(
		__("QA Coverage: {0}%", [format_number(frm.doc.qa_coverage_percent || 0, null, 1)]),
		frm.doc.qa_coverage_percent >= 80 ? "green" : "orange"
	);
}
