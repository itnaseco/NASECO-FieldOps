// Copyright (c) 2026, Naseco and contributors
// For license information, please see license.txt

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
  refresh(frm) {
    set_stage_options(frm);
    sync_input_stage_indexes(frm);
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
