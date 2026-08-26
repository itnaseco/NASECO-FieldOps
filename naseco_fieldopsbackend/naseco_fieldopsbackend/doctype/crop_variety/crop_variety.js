frappe.ui.form.on('Crop Variety', {
    setup(frm) {
        frm.set_query('seed_category', 'seed_items', () => ({ filters: { enabled: 1 } }));
        frm.set_query('seed_class', 'seed_items', () => ({ filters: { enabled: 1 } }));
        frm.set_query('item_code', 'seed_items', () => ({
            filters: { disabled: 0, is_stock_item: 1 }
        }));
    },

    refresh(frm) {
        if (frm.is_new() || !frappe.model.can_create('Item')) return;
        frm.add_custom_button(__('Create Seed Item'), () => show_seed_item_dialog(frm), __('Create'));
    }
});

function show_seed_item_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Create and Map Seed Item'),
        fields: [
            { fieldname: 'item_code', fieldtype: 'Data', label: __('Item Code'), reqd: 1 },
            { fieldname: 'item_name', fieldtype: 'Data', label: __('Item Name'), reqd: 1 },
            { fieldname: 'item_group', fieldtype: 'Link', options: 'Item Group', label: __('Item Group'), reqd: 1 },
            { fieldname: 'stock_uom', fieldtype: 'Link', options: 'UOM', label: __('Stock UOM'), reqd: 1, default: 'Kg' },
            { fieldname: 'seed_category', fieldtype: 'Link', options: 'Seed Category', label: __('Seed Category'), reqd: 1, get_query: () => ({ filters: { enabled: 1 } }) },
            { fieldname: 'seed_class', fieldtype: 'Link', options: 'Seed Class', label: __('Seed Class'), reqd: 1, get_query: () => ({ filters: { enabled: 1 } }) },
            { fieldname: 'item_purpose', fieldtype: 'Select', options: 'Parent Seed\nRaw Seed\nFinished Seed', label: __('Item Purpose'), reqd: 1 },
            { fieldname: 'is_default', fieldtype: 'Check', label: __('Default for this Category and Purpose'), default: 1 }
        ],
        primary_action_label: __('Create Item'),
        primary_action(values) {
            frappe.call({
                method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.crop_variety.crop_variety.create_seed_item',
                args: { variety: frm.doc.name, ...values },
                freeze: true,
                callback(r) {
                    if (!r.exc) {
                        dialog.hide();
                        frm.reload_doc();
                        frappe.show_alert({ message: __('Seed Item {0} created and mapped', [r.message]), indicator: 'green' });
                    }
                }
            });
        }
    });
    dialog.show();
}
