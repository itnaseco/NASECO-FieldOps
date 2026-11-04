// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

const PARENT_SEED_ROLES = ["Female", "Male"];

function ensure_parent_seed_rows(frm, variety) {
  if (!variety || frm.doc.variety_scope !== "Selected Varieties") return;
  PARENT_SEED_ROLES.forEach((parentRole) => {
    const exists = (frm.doc.parent_seed_items || []).some(
      (row) => row.variety === variety && row.parent_role === parentRole
    );
    if (!exists) {
      const row = frm.add_child("parent_seed_items");
      row.variety = variety;
      row.parent_role = parentRole;
      row.ratio_group = "Primary";
      row.recovery_policy = "Fully Recoverable";
      row.recoverable_percent = 100;
    }
  });
  frm.refresh_field("parent_seed_items");
}

function parent_seed_row_is_configured(row) {
  return Boolean(
	row.item_code || row.lot_analysis || flt(row.germination_percent) ||
	flt(row.thousand_kernel_weight_g) || flt(row.ratio_value) ||
	flt(row.quantity_per_hectare) || row.uom || row.source_warehouse
  );
}

function remove_incomplete_parent_seed_rows(frm, variety) {
  frm.doc.parent_seed_items = (frm.doc.parent_seed_items || []).filter(
    (row) => row.variety !== variety || parent_seed_row_is_configured(row)
  );
  frm.refresh_field("parent_seed_items");
}

function prepare_all_parent_seed_rows(frm) {
  (frm.doc.applicable_varieties || [])
    .filter((row) => row.enabled && row.variety)
    .forEach((row) => ensure_parent_seed_rows(frm, row.variety));
}

function set_stage_options(frm) {
  const stages = (frm.doc.stages || [])
    .map((s) => s.stage_name)
    .filter((v) => v);
  const options = stages.join("\n");

  const grid = frm.get_field("inputs") && frm.get_field("inputs").grid;
  if (grid) {
    grid.update_docfield_property("recipe_stage", "options", options);
    grid.refresh();
  }
}

function sync_input_stage_indexes(frm) {
  const stageIndexByName = {};
  (frm.doc.stages || []).forEach((s) => {
    if (s.stage_name) {
      stageIndexByName[s.stage_name] = s.order_index || s.idx;
    }
  });

  (frm.doc.inputs || []).forEach((row) => {
    if (row.recipe_stage && stageIndexByName[row.recipe_stage]) {
      row.stage_index = stageIndexByName[row.recipe_stage];
    }
  });

  frm.refresh_field("inputs");
}

function stage_day_number(row) {
  if (row.start_day_offset == null || row.end_day_offset == null) return null;
  const start = cint(row.start_day_offset);
  const end = cint(row.end_day_offset);
  if (end < start) return null;
  if (start < 0) {
    const daysPrior = Math.abs(start);
    return daysPrior === 1
      ? __("1 Day Prior")
      : __("{0} Days Prior", [daysPrior]);
  }
  return start === 0 && end === 0 ? "1" : String(end);
}

function refresh_stage_day_number(cdt, cdn) {
  const row = locals[cdt][cdn];
  frappe.model.set_value(cdt, cdn, "day_number", stage_day_number(row));
}

function parent_seed_status_indicator(status) {
  const colors = {
    Prepared: "green",
    Outdated: "orange",
    "Not Prepared": "red",
    "Legacy Preserved": "blue",
  };
  return `<span class="indicator-pill ${colors[status] || "gray"}">${__(status || "Not Prepared")}</span>`;
}

function render_parent_seed_summary(frm) {
  const wrapper = frm.get_field("parent_seed_preparation_summary")?.$wrapper;
  if (!wrapper) return;
  const rows = frm.doc.parent_seed_items || [];
  const status = frm.doc.parent_seed_preparation_status ||
    (frm.doc.parent_seed_calculation_method === "Legacy Fixed Kg/Ha" && rows.length
      ? "Legacy Preserved"
      : "Not Prepared");
  const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
  const format = (value, precision = 2) => format_number(flt(value), null, precision);
  const formatOptional = (value, precision = 2, suffix = "") =>
    value == null || value === "" ? "&mdash;" : `${format(value, precision)}${suffix}`;
  const metadata = [
    [__("Calculation"), frm.doc.parent_seed_calculation_method || __("Determined during preparation")],
    [__("Expected Plants/Ha"), formatOptional(frm.doc.expected_plants_per_hectare, 0)],
    [__("Operational Allowance"), formatOptional(frm.doc.seed_requirement_allowance_percent, 1, "%")],
    [__("Formula Version"), frm.doc.parent_seed_formula_version || "—"],
    [__("Prepared By"), frm.doc.parent_seed_prepared_by || "—"],
    [__("Prepared On"), frm.doc.parent_seed_prepared_on
      ? frappe.datetime.str_to_user(frm.doc.parent_seed_prepared_on)
      : "—"],
  ];
  const metadataHtml = metadata.map(([label, value]) => `
    <div class="col-sm-6 col-lg-4 mb-3">
      <div class="text-muted small">${escape(label)}</div>
      <div class="font-weight-bold">${value === "&mdash;" ? value : escape(value)}</div>
    </div>`).join("");
  if (!rows.length) {
    wrapper.html(`
      <div class="border rounded p-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h5 class="mb-0">${__("Parent Seed Requirements")}</h5>
          ${parent_seed_status_indicator(status)}
        </div>
        <p class="text-muted mb-0">${__("No prepared parent-seed snapshot exists. Use Actions > Prepare Parent Seed Rows to define the calculation method, plant population, allowance, ratios, evidence and seed Items.")}</p>
      </div>`);
    return;
  }
  wrapper.html(`
    <div class="mb-3 d-flex justify-content-between align-items-center">
      <h5 class="mb-0">${__("Parent Seed Requirements")}</h5>
      <div>${parent_seed_status_indicator(status)}</div>
    </div>
    <div class="row">${metadataHtml}</div>
  `);
}

function mark_parent_seed_preparation_outdated(frm) {
  if (frm.doc.parent_seed_preparation_status !== "Prepared") return;
  frm.doc.parent_seed_preparation_status = "Outdated";
  frm.refresh_field("parent_seed_preparation_status");
  render_parent_seed_summary(frm);
}

function build_parent_seed_preview_html(message) {
  const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
  const format = (value, precision = 2) => format_number(flt(value), null, precision);
  const rows = (message.rows || []).map((row) => `<tr>
    <td>${escape(row.variety)}</td><td>${escape(row.parent_role)}</td>
    <td>${escape(row.parent_variety)}</td><td>${escape(row.item_code)}</td>
    <td>${escape(row.item_selection_source)}</td><td class="text-right">${format(row.ratio_value, 0)}</td>
    <td class="text-right">${format(row.expected_plants_per_hectare, 0)}</td>
    <td class="text-right">${format(row.required_kernels_per_hectare, 0)}</td>
    <td class="text-right">${format(row.base_quantity_per_hectare, 1)}</td>
    <td class="text-right"><strong>${format(row.quantity_per_hectare, 1)}</strong></td>
  </tr>`).join("");
  const warnings = (message.warnings || []).length
    ? `<div class="alert alert-warning"><strong>${__("Review before confirming")}</strong><ul class="mb-0">${message.warnings.map((warning) => `<li>${escape(warning)}</li>`).join("")}</ul></div>`
    : "";
  return `${warnings}<div class="table-responsive"><table class="table table-bordered table-sm">
    <thead><tr><th>${__("Output Variety")}</th><th>${__("Role")}</th><th>${__("Parent Variety")}</th>
    <th>${__("Seed Item")}</th><th>${__("Item Selected By")}</th>
    <th>${__("Ratio")}</th><th>${__("Plants/Ha")}</th><th>${__("Required Kernels/Ha")}</th>
    <th>${__("Base Kg/Ha")}</th><th>${__("Planned Kg/Ha")}</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function hydrate_parent_seed_lot_analysis(control) {
  const row = control.doc;
  if (!row?.lot_analysis) return;
  return frappe.db.get_doc("Parent Seed Lot Analysis", row.lot_analysis).then((analysis) => {
    const values = {
      calculation_basis: "Approved Lot Analysis",
      item_code: analysis.item_code,
      item_selection_source: "Approved Lot Analysis",
      germination_percent: analysis.germination_percent,
      thousand_kernel_weight_g: analysis.thousand_kernel_weight_g,
      batch_no: analysis.batch_no,
      analysis_test_date: analysis.test_date,
      analysis_valid_until: analysis.valid_until,
    };
    Object.assign(row, values);
    control.grid_row?.refresh();
    frappe.show_alert({
      message: __("Germination, thousand-kernel weight and Item fetched from {0}.", [analysis.name]),
      indicator: "green",
    });
  });
}

function open_parent_seed_preparation_wizard(frm) {
  if (frm.is_new()) {
    frappe.msgprint(__("Save the Crop Recipe and its applicable varieties before preparing parent-seed requirements."));
    return;
  }
  frappe.call({
    method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.get_parent_seed_preparation_context",
    args: { recipe_name: frm.doc.name },
    freeze: true,
    freeze_message: __("Loading parent-seed configuration..."),
    callback({ message: context }) {
      if (!context) return;
      const varietyData = Object.entries(context.variety_populations || {}).map(([variety, population]) => ({
        variety,
        expected_plants_per_hectare_override: population || 0,
      }));
      const parentFields = [
        { fieldname: "variety", fieldtype: "Link", options: "Crop Variety", label: __("Output Variety"), read_only: 1, in_list_view: 1 },
        { fieldname: "parent_role", fieldtype: "Data", label: __("Role"), read_only: 1, in_list_view: 1 },
        { fieldname: "parentage", fieldtype: "Link", options: "Seed Variety Parentage", label: __("Parentage"), read_only: 1 },
        { fieldname: "parent_variety", fieldtype: "Link", options: "Crop Variety", label: __("Parent Variety"), read_only: 1, in_list_view: 1 },
        { fieldname: "required_seed_category", fieldtype: "Link", options: "Seed Category", label: __("Seed Category"), read_only: 1 },
        { fieldname: "required_seed_class", fieldtype: "Link", options: "Seed Class", label: __("Seed Class"), read_only: 1 },
        { fieldname: "ratio_value", fieldtype: "Int", label: __("Ratio"), reqd: 1, in_list_view: 1 },
        { fieldname: "calculation_basis", fieldtype: "Select", options: "Recipe Planning Assumption\nApproved Lot Analysis", label: __("Calculation Basis"), reqd: 1, in_list_view: 1 },
        { fieldname: "lot_analysis", fieldtype: "Link", options: "Parent Seed Lot Analysis", label: __("Parent Seed Lot Analysis"), in_list_view: 1, onchange() { return hydrate_parent_seed_lot_analysis(this); } },
        { fieldname: "item_code", fieldtype: "Link", options: "Item", label: __("Parent Seed Item"), in_list_view: 1, read_only_depends_on: "eval:doc.calculation_basis=='Approved Lot Analysis'" },
        { fieldname: "germination_percent", fieldtype: "Percent", label: __("Germination %"), precision: 1, in_list_view: 1, read_only_depends_on: "eval:doc.calculation_basis=='Approved Lot Analysis'" },
        { fieldname: "thousand_kernel_weight_g", fieldtype: "Float", label: __("Thousand-Kernel Weight (g)"), precision: 1, in_list_view: 1, read_only_depends_on: "eval:doc.calculation_basis=='Approved Lot Analysis'" },
        { fieldname: "assumption_source", fieldtype: "Data", label: __("Assumption Source"), depends_on: "eval:doc.calculation_basis=='Recipe Planning Assumption'" },
        { fieldname: "assumption_reason", fieldtype: "Small Text", label: __("Assumption Reason"), depends_on: "eval:doc.calculation_basis=='Recipe Planning Assumption'" },
        { fieldname: "recovery_policy", fieldtype: "Select", options: "Fully Recoverable\nPartially Recoverable\nCompany Subsidy\nNon-Recoverable\nReturnable", label: __("Recovery Policy") },
        { fieldname: "recoverable_percent", fieldtype: "Percent", label: __("Recoverable %"), precision: 1 },
        { fieldname: "source_warehouse", fieldtype: "Link", options: "Warehouse", label: __("Source Warehouse") },
      ];
      const dialog = new frappe.ui.Dialog({
        title: __("Prepare Parent Seed Requirements"),
        size: "extra-large",
        fields: [
          { fieldtype: "HTML", fieldname: "step_help", options: `<div class="alert alert-info">${__("Step 1: confirm population targets. Step 2: configure Female and Male evidence. Step 3: preview and confirm the calculated snapshot.")}</div>` },
          { fieldtype: "Section Break", label: __("Step 1 - Population and Allowance") },
          { fieldname: "parent_seed_calculation_method", fieldtype: "Select", label: __("Parent Seed Calculation"), options: "Ratio and Lot Analysis", reqd: 1, read_only: 1, default: context.parent_seed_calculation_method || "Ratio and Lot Analysis", description: __("Preparing a snapshot converts this recipe version to the governed ratio-based calculation model. Existing legacy quantities remain unchanged until confirmation.") },
          { fieldname: "expected_plants_per_hectare", fieldtype: "Int", label: __("Default Expected Plants per Hectare"), reqd: 1, default: context.expected_plants_per_hectare },
          { fieldname: "seed_requirement_allowance_percent", fieldtype: "Percent", label: __("Operational Seed Allowance %"), precision: 1, default: context.seed_requirement_allowance_percent },
          { fieldname: "variety_populations", fieldtype: "Table", label: __("Per-Variety Population Overrides"), cannot_add_rows: 1, cannot_delete_rows: 1, data: varietyData, fields: [
            { fieldname: "variety", fieldtype: "Link", options: "Crop Variety", label: __("Production Variety"), read_only: 1, in_list_view: 1 },
            { fieldname: "expected_plants_per_hectare_override", fieldtype: "Int", label: __("Plants/Ha Override"), in_list_view: 1 },
          ] },
          { fieldtype: "Section Break", label: __("Step 2 - Parent Ratios and Evidence") },
          { fieldname: "parent_rows", fieldtype: "Table", label: __("Parent Seed Components"), cannot_add_rows: 1, cannot_delete_rows: 1, data: context.rows, fields: parentFields },
          { fieldtype: "Section Break", label: __("Step 3 - Calculation Preview") },
          { fieldtype: "HTML", fieldname: "preview_html", options: `<div class="text-muted">${__("Select Preview to calculate and validate the requirements.")}</div>` },
        ],
      });
      const lotField = dialog.fields_dict.parent_rows.grid.get_field("lot_analysis");
      lotField.get_query = (doc) => {
		const row = doc || {};
        return { filters: {
          docstatus: 1, status: "Approved", parent_variety: row.parent_variety,
          seed_category: row.required_seed_category, seed_class: row.required_seed_class || undefined,
        }};
      };
      const itemField = dialog.fields_dict.parent_rows.grid.get_field("item_code");
      itemField.get_query = (doc) => {
		const row = doc || {};
        return {
          query: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.parent_seed_item_query",
          filters: { variety: row.variety, parent_variety: row.parent_variety, seed_category: row.required_seed_category, seed_class: row.required_seed_class, crop: frm.doc.crop },
        };
      };
      let preview = null;
      const payload = () => {
        const values = dialog.get_values();
        if (!values) return null;
        return {
          settings: {
            parent_seed_calculation_method: values.parent_seed_calculation_method,
            expected_plants_per_hectare: values.expected_plants_per_hectare,
            seed_requirement_allowance_percent: values.seed_requirement_allowance_percent,
            variety_populations: Object.fromEntries((values.variety_populations || []).map((row) => [row.variety, row.expected_plants_per_hectare_override || 0])),
          },
          rows: values.parent_rows || [],
        };
      };
      const showConfigure = () => {
        preview = null;
        dialog.fields_dict.preview_html.$wrapper.html(`<div class="text-muted">${__("Select Preview to calculate and validate the requirements.")}</div>`);
        dialog.set_primary_action(__("Preview Calculations"), previewAction);
        dialog.set_secondary_action_label(__("Close"));
        dialog.set_secondary_action(() => dialog.hide());
      };
      const previewAction = () => {
        const data = payload();
        if (!data) return;
        frappe.call({
          method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.preview_parent_seed_preparation",
          args: { recipe_name: frm.doc.name, settings: data.settings, rows: data.rows },
          freeze: true,
          freeze_message: __("Calculating parent-seed requirements..."),
          callback({ message }) {
            if (!message) return;
            preview = { message, data };
            dialog.fields_dict.preview_html.$wrapper.html(build_parent_seed_preview_html(message));
            dialog.set_primary_action(__("Confirm Preparation"), commitAction);
            dialog.set_secondary_action_label(__("Back to Configuration"));
            dialog.set_secondary_action(showConfigure);
          },
        });
      };
      const commitAction = () => {
        if (!preview) return;
        frappe.call({
          method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.commit_parent_seed_preparation",
          args: { recipe_name: frm.doc.name, expected_modified: context.modified, settings: preview.data.settings, rows: preview.data.rows },
          freeze: true,
          freeze_message: __("Saving prepared parent-seed requirements..."),
          callback({ message }) {
            if (!message) return;
            dialog.hide();
            frm.reload_doc().then(() => {
              frappe.show_alert({ message: __("Parent-seed requirements prepared and frozen as a recipe snapshot."), indicator: "green" });
            });
          },
        });
      };
      showConfigure();
      dialog.show();
    },
  });
}

frappe.ui.form.on("Crop Recipe", {
  setup(frm) {
    frm.set_query("variety", "applicable_varieties", () => ({ filters: { crop: frm.doc.crop } }));
    frm.set_query("variety", "parent_seed_items", () => ({ filters: { crop: frm.doc.crop } }));
    frm.set_query("item_code", "parent_seed_items", (doc, cdt, cdn) => ({
      query: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.parent_seed_item_query",
	  filters: {
		variety: locals[cdt][cdn].variety,
		parent_variety: locals[cdt][cdn].parent_variety,
		seed_category: locals[cdt][cdn].required_seed_category,
		seed_class: locals[cdt][cdn].required_seed_class,
		crop: frm.doc.crop
	  }
    }));
	frm.set_query("parentage", "parent_seed_items", (doc, cdt, cdn) => ({
	  filters: { output_variety: locals[cdt][cdn].variety, docstatus: 1, status: "Active" }
	}));
	frm.set_query("lot_analysis", "parent_seed_items", (doc, cdt, cdn) => {
	  const row = locals[cdt][cdn];
	  return {
		filters: {
		  docstatus: 1,
		  status: "Approved",
		  parent_variety: row.parent_variety,
		  seed_category: row.required_seed_category,
		  seed_class: row.required_seed_class,
		  item_code: row.item_code || undefined
		}
	  };
	});
  },
  onload(frm) {
	  if (frm.is_new() && !frm.doc.parent_seed_calculation_method) {
		frm.set_value("parent_seed_calculation_method", "Ratio and Lot Analysis");
	  }
	},
  expected_plants_per_hectare: mark_parent_seed_preparation_outdated,
  seed_requirement_allowance_percent: mark_parent_seed_preparation_outdated,
  parent_seed_calculation_method(frm) {
    mark_parent_seed_preparation_outdated(frm);
    render_parent_seed_summary(frm);
  },
  refresh(frm) {
    set_stage_options(frm);
    sync_input_stage_indexes(frm);
    render_parent_seed_summary(frm);
    if (frm.doc.docstatus === 0 && frm.doc.variety_scope === "Selected Varieties") {
      const actionLabel = (frm.doc.parent_seed_items || []).length
        ? __("Reprepare Parent Seed Rows")
        : __("Prepare Parent Seed Rows");
      frm.add_custom_button(actionLabel, () => {
        open_parent_seed_preparation_wizard(frm);
      }, __("Actions"));
    }
    if (!frm.is_new() && frappe.user.has_role(["Outgrower Manager", "System Manager"])) {
      frm.add_custom_button(__("Clone Recipe Version"), () => {
        frappe.prompt([
          { fieldname: "recipe_name", fieldtype: "Data", label: __("New Recipe Name"), reqd: 1 },
          { fieldname: "recipe_version", fieldtype: "Data", label: __("New Version"), reqd: 1 },
        ], (values) => {
          frappe.call({
            method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.clone_recipe",
            args: { source_recipe: frm.doc.name, ...values },
            callback: (r) => r.message && frappe.set_route("Form", "Crop Recipe", r.message),
          });
        }, __("Clone Recipe"), __("Create"));
      });
    }
  },
  before_applicable_varieties_remove(frm, cdt, cdn) {
    if (frm.doc.parent_seed_preparation_status === "Prepared") {
      frm.doc.parent_seed_preparation_status = "Outdated";
      frm.refresh_field("parent_seed_preparation_status");
    }
  },
  applicable_varieties_remove(frm) {
    render_parent_seed_summary(frm);
  },
  stages_add(frm) {
    set_stage_options(frm);
    sync_input_stage_indexes(frm);
  },
  stages_remove(frm) {
    set_stage_options(frm);
    sync_input_stage_indexes(frm);
  },
});

function populate_parent_from_parentage(frm, cdt, cdn) {
  const row = locals[cdt][cdn];
  if (!row.parentage || !row.parent_role) return;
  frappe.call({
	method: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.get_parentage_parent",
	args: { parentage: row.parentage, parent_role: row.parent_role },
	callback({ message }) {
	  if (!message) return;
	  const selectedAnalysisIsCompatible =
		row.parent_variety === message.parent_variety &&
		row.required_seed_category === message.required_seed_category &&
		(row.required_seed_class || null) === (message.required_seed_class || null);
	  if (!selectedAnalysisIsCompatible && row.lot_analysis) {
		frappe.model.set_value(cdt, cdn, "lot_analysis", null);
	  }
	  frappe.model.set_value(cdt, cdn, "variety", message.output_variety);
	  frappe.model.set_value(cdt, cdn, "parent_variety", message.parent_variety);
	  frappe.model.set_value(cdt, cdn, "required_seed_category", message.required_seed_category);
	  frappe.model.set_value(cdt, cdn, "required_seed_class", message.required_seed_class);
	}
  });
}

frappe.ui.form.on("Recipe Parent Seed Item", {
  parentage: populate_parent_from_parentage,
  parent_role: populate_parent_from_parentage,
  calculation_basis(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (row.calculation_basis === "Recipe Planning Assumption") {
	  frappe.model.set_value(cdt, cdn, "lot_analysis", null);
	  frappe.model.set_value(cdt, cdn, "batch_no", null);
	  frappe.model.set_value(cdt, cdn, "analysis_test_date", null);
	  frappe.model.set_value(cdt, cdn, "analysis_valid_until", null);
	}
  },
  lot_analysis(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.lot_analysis) return;
	frappe.db.get_doc("Parent Seed Lot Analysis", row.lot_analysis).then((analysis) => {
	  frappe.run_serially([
		() => frappe.model.set_value(cdt, cdn, "calculation_basis", "Approved Lot Analysis"),
		() => frappe.model.set_value(cdt, cdn, "parent_variety", analysis.parent_variety),
		() => frappe.model.set_value(cdt, cdn, "required_seed_category", analysis.seed_category),
		() => frappe.model.set_value(cdt, cdn, "required_seed_class", analysis.seed_class),
		() => frappe.model.set_value(cdt, cdn, "item_code", analysis.item_code),
		() => frappe.model.set_value(cdt, cdn, "batch_no", analysis.batch_no),
		() => frappe.model.set_value(cdt, cdn, "germination_percent", analysis.germination_percent),
		() => frappe.model.set_value(cdt, cdn, "thousand_kernel_weight_g", analysis.thousand_kernel_weight_g),
		() => frappe.model.set_value(cdt, cdn, "analysis_test_date", analysis.test_date),
		() => frappe.model.set_value(cdt, cdn, "analysis_valid_until", analysis.valid_until)
	  ]);
	});
  },
  ratio_value(frm) {
	frm.dirty();
  }
});

frappe.ui.form.on("Crop Recipe Variety", {
  variety(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.enabled && row.variety && frm.doc.parent_seed_preparation_status === "Prepared") {
      frm.doc.parent_seed_preparation_status = "Outdated";
      frm.refresh_field("parent_seed_preparation_status");
    }
  },
  enabled(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (frm.doc.parent_seed_preparation_status === "Prepared") {
      frm.doc.parent_seed_preparation_status = "Outdated";
      frm.refresh_field("parent_seed_preparation_status");
    }
  },
  expected_plants_per_hectare_override(frm) {
    if (frm.doc.parent_seed_preparation_status === "Prepared") {
      frm.doc.parent_seed_preparation_status = "Outdated";
      frm.refresh_field("parent_seed_preparation_status");
    }
  },
});

frappe.ui.form.on("Recipe Stage", {
  stage_name(frm) {
    set_stage_options(frm);
    sync_input_stage_indexes(frm);
  },
  order_index(frm) {
    sync_input_stage_indexes(frm);
  },
  start_day_offset(frm, cdt, cdn) {
    refresh_stage_day_number(cdt, cdn);
  },
  end_day_offset(frm, cdt, cdn) {
    refresh_stage_day_number(cdt, cdn);
  },
});

frappe.ui.form.on("Recipe Input Item", {
  form_render(frm, cdt, cdn) {
    set_stage_options(frm);
  },
  recipe_stage(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const stages = frm.doc.stages || [];
    const match = stages.find((s) => s.stage_name === row.recipe_stage);
    row.stage_index = match ? match.order_index || match.idx : null;
    frm.refresh_field("inputs");
  },
  item_code(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.item_code) return;
    frappe.db.get_value('Item', row.item_code, ['item_name', 'stock_uom'])
      .then((r) => {
        if (!r.message) return;
        frappe.model.set_value(cdt, cdn, 'input_name', r.message.item_name);
        frappe.model.set_value(cdt, cdn, 'unit', r.message.stock_uom);
        frappe.model.set_value(cdt, cdn, 'stock_uom', r.message.stock_uom);
        frappe.model.set_value(cdt, cdn, 'conversion_factor', 1);
      });
  },
  unit(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.item_code || !row.unit) return;
    frappe.call({
      method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.stage_input_request.stage_input_request.get_item_uom_details',
      args: { item_code: row.item_code, uom: row.unit },
      callback({ message }) {
        if (!message) return;
        frappe.model.set_value(cdt, cdn, 'stock_uom', message.stock_uom);
        frappe.model.set_value(cdt, cdn, 'conversion_factor', message.conversion_factor);
        frappe.model.set_value(
          cdt,
          cdn,
          'stock_quantity_per_hectare',
          flt(row.quantity_per_hectare) * flt(message.conversion_factor)
        );
      }
    });
  },
  quantity_per_hectare(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    frappe.model.set_value(cdt, cdn, "stock_quantity_per_hectare", flt(row.quantity_per_hectare) * flt(row.conversion_factor || 1));
    frappe.model.set_value(cdt, cdn, "quantity_per_acre", flt(row.quantity_per_hectare) * 0.40468564224);
  },
  quantity_per_acre(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    frappe.model.set_value(
      cdt,
      cdn,
      'stock_quantity_per_hectare',
      flt(row.quantity_per_hectare) * flt(row.conversion_factor || 1)
    );
  },
  recovery_policy(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.recovery_policy === 'Fully Recoverable') {
      frappe.model.set_value(cdt, cdn, 'recoverable_percent', 100);
    } else if (['Company Subsidy', 'Non-Recoverable'].includes(row.recovery_policy)) {
      frappe.model.set_value(cdt, cdn, 'recoverable_percent', 0);
    }
  },
});
