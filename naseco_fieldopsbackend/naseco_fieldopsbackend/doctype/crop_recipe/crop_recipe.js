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
  return Boolean(row.item_code || flt(row.ratio_value) || flt(row.quantity_per_hectare) || row.uom || row.source_warehouse);
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

frappe.ui.form.on("Crop Recipe", {
  setup(frm) {
    frm.set_query("variety", "applicable_varieties", () => ({ filters: { crop: frm.doc.crop } }));
    frm.set_query("variety", "parent_seed_items", () => ({ filters: { crop: frm.doc.crop } }));
    frm.set_query("item_code", "parent_seed_items", (doc, cdt, cdn) => ({
      query: "naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_recipe.crop_recipe.parent_seed_item_query",
      filters: { variety: locals[cdt][cdn].variety, crop: frm.doc.crop }
    }));
  },
  refresh(frm) {
    set_stage_options(frm);
    sync_input_stage_indexes(frm);
    if (frm.doc.docstatus === 0 && frm.doc.variety_scope === "Selected Varieties") {
      frm.add_custom_button(__("Prepare Parent Seed Rows"), () => {
        prepare_all_parent_seed_rows(frm);
        frappe.show_alert({ message: __("Female and Male parent-seed rows prepared"), indicator: "green" });
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
    const variety = locals[cdt][cdn].variety;
    const configured = (frm.doc.parent_seed_items || []).some(
      (row) => row.variety === variety && parent_seed_row_is_configured(row)
    );
    if (configured) {
      frappe.throw(__("Remove the configured parent-seed rows for {0} before removing this applicable variety.", [variety]));
    }
    frm._removed_applicable_variety = variety;
  },
  applicable_varieties_remove(frm) {
    if (frm._removed_applicable_variety) {
      remove_incomplete_parent_seed_rows(frm, frm._removed_applicable_variety);
      frm._removed_applicable_variety = null;
    }
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

frappe.ui.form.on("Crop Recipe Variety", {
  variety(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.enabled && row.variety) ensure_parent_seed_rows(frm, row.variety);
  },
  enabled(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.enabled && row.variety) {
      ensure_parent_seed_rows(frm, row.variety);
      return;
    }
    const configured = (frm.doc.parent_seed_items || []).some(
      (parentRow) => parentRow.variety === row.variety && parent_seed_row_is_configured(parentRow)
    );
    if (configured) {
      row.enabled = 1;
      frm.refresh_field("applicable_varieties");
      frappe.msgprint(__("Remove the configured parent-seed rows for {0} before disabling this variety.", [row.variety]));
    } else {
      remove_incomplete_parent_seed_rows(frm, row.variety);
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
