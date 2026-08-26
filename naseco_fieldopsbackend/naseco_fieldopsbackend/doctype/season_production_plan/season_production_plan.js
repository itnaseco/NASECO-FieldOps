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
		frm.set_query("production_category", "production_targets", () => ({ filters: { enabled: 1 } }));
		frm.set_query("seed_class", "production_targets", () => ({ filters: { enabled: 1 } }));
		frm.set_query("outgrower_supervisor", "production_targets", () => ({
			query: "naseco_fieldopsbackend.roles.user_with_role_query",
			filters: { role: "Outgrower Supervisor" }
		}));
		frm.set_query("variety", "production_targets", (doc, cdt, cdn) => ({
			filters: { crop: locals[cdt][cdn].crop }
		}));
		frm.set_query("crop_recipe", "production_targets", (doc, cdt, cdn) => ({
			query: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.applicable_recipe_query",
			filters: { crop: locals[cdt][cdn].crop, variety: locals[cdt][cdn].variety }
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
	variety(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.crop_recipe) frm.script_manager.trigger("crop_recipe", cdt, cdn);
	},
	crop_recipe(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.crop_recipe) {
			frappe.model.set_value(cdt, cdn, "recipe_yield_kg_per_hectare", 0);
			frappe.model.set_value(cdt, cdn, "planned_yield_kg_per_hectare", 0);
			frappe.model.set_value(cdt, cdn, "yield_source_recipe", null);
			frappe.model.set_value(cdt, cdn, "yield_override_reason", null);
			return;
		}
		const selectedRecipe = row.crop_recipe;
		frappe.call({
			method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.get_recipe_target_defaults",
			args: { recipe_name: selectedRecipe, variety: row.variety }
		}).then(({ message }) => {
				if (locals[cdt][cdn].crop_recipe !== selectedRecipe) return;
				const recipeYield = flt(message && message.expected_yield_kg_per_hectare);
				frappe.model.set_value(cdt, cdn, "recipe_yield_kg_per_hectare", recipeYield);
				frappe.model.set_value(cdt, cdn, "planned_yield_kg_per_hectare", recipeYield);
				frappe.model.set_value(cdt, cdn, "yield_source_recipe", selectedRecipe);
				frappe.model.set_value(cdt, cdn, "yield_override_reason", null);
			});
	},
	target_hectares: calculate_target,
	planned_yield_kg_per_hectare: calculate_target,
});

function calculate_target(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const plannedProduction = flt(row.target_hectares) * flt(row.planned_yield_kg_per_hectare);
	frappe.model.set_value(cdt, cdn, "planned_production_qty", plannedProduction);
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
