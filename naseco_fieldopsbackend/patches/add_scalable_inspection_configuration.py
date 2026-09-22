import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


CONFIG_DOCTYPES = (
	"Inspection Attribute",
	"Inspection Parameter",
	"Inspection Standard",
	"Inspection Template",
)


def execute():
	_create_take_evidence_doctype()
	create_custom_fields(
		{
			"Inspection Attribute": [
				{"fieldname": "attribute_code", "label": "Attribute Code", "fieldtype": "Data", "unique": 1, "insert_after": "attribute_name"},
				{"fieldname": "attribute_group", "label": "Attribute Group", "fieldtype": "Select", "options": "Plant Population\nPest\nDisease\nPurity\nWeed\nDetasselling\nIsolation\nInspection Quality", "insert_after": "attribute_code"},
				{"fieldname": "active", "label": "Active", "fieldtype": "Check", "default": "1", "insert_after": "attribute_group"},
			],
			"Inspection Parameter": [
				{"fieldname": "inspection_attribute", "label": "Inspection Attribute", "fieldtype": "Link", "options": "Inspection Attribute", "insert_after": "parameter_code"},
				{"fieldname": "evidence_policy", "label": "Evidence Policy", "fieldtype": "Select", "options": "None\nOptional\nRequired\nRequired on Non-zero\nRequired on Failure", "default": "None", "insert_after": "requires_take_counts"},
				{"fieldname": "minimum_evidence_files", "label": "Minimum Evidence Files", "fieldtype": "Int", "default": "0", "non_negative": 1, "insert_after": "evidence_policy"},
				{"fieldname": "maximum_evidence_files", "label": "Maximum Evidence Files", "fieldtype": "Int", "default": "10", "non_negative": 1, "insert_after": "minimum_evidence_files"},
				{"fieldname": "allow_multiple_files", "label": "Allow Multiple Files", "fieldtype": "Check", "default": "1", "insert_after": "maximum_evidence_files"},
				{"fieldname": "decimal_precision", "label": "Decimal Precision", "fieldtype": "Int", "default": "2", "non_negative": 1, "insert_after": "allow_multiple_files"},
				{"fieldname": "active", "label": "Active", "fieldtype": "Check", "default": "1", "insert_after": "decimal_precision"},
			],
			"Inspection Template": [
				{"fieldname": "configuration_version", "label": "Configuration Version", "fieldtype": "Int", "default": "1", "read_only": 1, "insert_after": "template_name"},
				{"fieldname": "lifecycle_status", "label": "Lifecycle Status", "fieldtype": "Select", "options": "Draft\nPublished\nRetired", "default": "Published", "insert_after": "configuration_version"},
				{"fieldname": "supersedes_template", "label": "Supersedes Template", "fieldtype": "Link", "options": "Inspection Template", "read_only": 1, "insert_after": "lifecycle_status"},
				{"fieldname": "effective_from", "label": "Effective From", "fieldtype": "Date", "insert_after": "supersedes_template"},
				{"fieldname": "effective_to", "label": "Effective To", "fieldtype": "Date", "insert_after": "effective_from"},
			],
			"Inspection": [
				{"fieldname": "template_version", "label": "Template Version", "fieldtype": "Int", "default": "1", "read_only": 1, "insert_after": "inspection_template"},
				{"fieldname": "configuration_snapshot", "label": "Configuration Snapshot", "fieldtype": "Long Text", "read_only": 1, "hidden": 1, "insert_after": "template_version"},
				{"fieldname": "take_evidence", "label": "Take Evidence", "fieldtype": "Table", "options": "Inspection Take Evidence", "insert_after": "take_results"},
			],
			"Crop Cycle": [
				{"fieldname": "verified_inter_row_spacing_m", "label": "Verified Inter-row Spacing (m)", "fieldtype": "Float", "read_only": 1, "precision": "3"},
				{"fieldname": "spacing_source_inspection", "label": "Spacing Source Inspection", "fieldtype": "Link", "options": "Inspection", "read_only": 1, "insert_after": "verified_inter_row_spacing_m"},
				{"fieldname": "spacing_verified_on", "label": "Spacing Verified On", "fieldtype": "Datetime", "read_only": 1, "insert_after": "spacing_source_inspection"},
			],
		},
		update=True,
	)
	make_property_setter(
		"Inspection Parameter",
		"parameter_group",
		"options",
		"Planting\nIsolation\nPurity\nPest\nDisease\nWeed\nDetassling\nHarvest\nInspection Quality",
		"Text",
	)
	_add_permissions()
	_seed_quality_configuration()
	_backfill_template_versions()
	_backfill_inspection_snapshots()


def _create_take_evidence_doctype():
	if frappe.db.exists("DocType", "Inspection Take Evidence"):
		return
	doc = frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Inspection Take Evidence",
			"module": "Naseco FieldOpsBackend",
			"custom": 1,
			"istable": 1,
			"editable_grid": 1,
			"fields": [
				{"fieldname": "external_id", "label": "Mobile Evidence ID", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
				{"fieldname": "take_number", "label": "Take Number", "fieldtype": "Int", "reqd": 1, "in_list_view": 1},
				{"fieldname": "parameter", "label": "Parameter", "fieldtype": "Link", "options": "Inspection Parameter", "in_list_view": 1},
				{"fieldname": "file", "label": "Evidence File", "fieldtype": "Attach", "reqd": 1, "in_list_view": 1},
				{"fieldname": "file_type", "label": "File Type", "fieldtype": "Data", "read_only": 1},
				{"fieldname": "caption", "label": "Caption", "fieldtype": "Small Text"},
				{"fieldname": "captured_at", "label": "Captured At", "fieldtype": "Datetime", "reqd": 1},
				{"fieldname": "captured_by", "label": "Captured By", "fieldtype": "Link", "options": "User", "read_only": 1},
				{"fieldname": "latitude", "label": "Latitude", "fieldtype": "Float", "precision": "7"},
				{"fieldname": "longitude", "label": "Longitude", "fieldtype": "Float", "precision": "7"},
				{"fieldname": "file_hash", "label": "File Hash", "fieldtype": "Data", "read_only": 1},
			],
		}
	)
	doc.insert(ignore_permissions=True)


def _add_permissions():
	for doctype in CONFIG_DOCTYPES:
		for role, write in (("Quality Manager", 1), ("Quality Inspector", 0)):
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				frappe.get_doc(
					{
						"doctype": "Custom DocPerm",
						"parent": doctype,
						"parenttype": "DocType",
						"parentfield": "permissions",
						"role": role,
						"permlevel": 0,
						"read": 1,
						"report": 1,
						"export": 1,
						"create": write,
						"write": write,
						"delete": write,
					}
				).insert(ignore_permissions=True)


def _seed_quality_configuration():
	attributes = {
		"Pest Infestation": {"attribute_code": "PEST_INFESTATION", "attribute_group": "Pest", "attribute_type": "Numeric", "unit": "Nos"},
		"Inter-row Spacing": {"attribute_code": "INTER_ROW_SPACING", "attribute_group": "Plant Population", "attribute_type": "Numeric", "unit": "Meter"},
	}
	for name, values in attributes.items():
		if not frappe.db.exists("Inspection Attribute", name):
			frappe.get_doc({"doctype": "Inspection Attribute", "attribute_name": name, "active": 1, **values}).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Inspection Attribute", name, {"active": 1, **values}, update_modified=False)

	parameters = {
		"Pest Infested Plants": {
			"parameter_code": "PEST_INFESTED_PLANTS", "inspection_attribute": "Pest Infestation", "parameter_group": "Pest",
			"data_type": "Count", "unit": "Nos", "applies_to": "Farmer", "measurement_scope": "Inspection Take",
			"calculation_method": "Cumulative Incidence", "denominator_basis": "Total Plants Counted", "requires_take_counts": 1,
			"evidence_policy": "Required on Non-zero", "minimum_evidence_files": 1, "maximum_evidence_files": 10,
			"description": "Count plants showing pest infestation in this take. Attach clear evidence when the count is above zero.",
		},
		"Inter-row Spacing": {
			"parameter_code": "INTER_ROW_SPACING_M", "inspection_attribute": "Inter-row Spacing", "parameter_group": "Planting",
			"data_type": "Number", "unit": "Meter", "applies_to": "Farmer", "measurement_scope": "Inspection Take",
			"calculation_method": "Direct Value", "requires_take_counts": 0, "evidence_policy": "Optional",
			"minimum_evidence_files": 0, "maximum_evidence_files": 5, "decimal_precision": 3,
			"description": "Measure the distance in metres between adjacent crop rows at this take.",
		},
	}
	for name, values in parameters.items():
		if not frappe.db.exists("Inspection Parameter", name):
			frappe.get_doc({"doctype": "Inspection Parameter", "parameter_name": name, "active": 1, **values}).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Inspection Parameter", name, {"active": 1, **values}, update_modified=False)

def _backfill_template_versions():
	frappe.db.sql("""
		update `tabInspection Template`
		set configuration_version = coalesce(nullif(configuration_version, 0), 1),
			lifecycle_status = coalesce(nullif(lifecycle_status, ''), 'Published')
	""")


def _backfill_inspection_snapshots():
	for row in frappe.get_all(
		"Inspection",
		filters={"inspection_template": ["is", "set"], "configuration_snapshot": ["is", "not set"]},
		fields=["name", "inspection_template"],
	):
		standards = frappe.get_all(
			"Inspection Standard",
			filters={"inspection_template": row.inspection_template},
			fields=["*"],
			order_by="creation asc, parameter asc",
		)
		parameter_names = sorted({item.parameter for item in standards if item.parameter})
		parameters = (
			frappe.get_all(
				"Inspection Parameter",
				filters={"name": ["in", parameter_names]},
				fields=["*"],
			)
			if parameter_names else []
		)
		snapshot = json.dumps(
			{
				"template": row.inspection_template,
				"version": frappe.db.get_value("Inspection Template", row.inspection_template, "configuration_version") or 1,
				"captured_at": str(frappe.utils.now_datetime()),
				"standards": [dict(item) for item in standards],
				"parameters": [dict(item) for item in parameters],
			},
			default=str,
			sort_keys=True,
		)
		frappe.db.set_value("Inspection", row.name, "configuration_snapshot", snapshot, update_modified=False)
	frappe.db.sql("""
		update `tabInspection` i
		left join `tabInspection Template` t on t.name = i.inspection_template
		set i.template_version = coalesce(nullif(i.template_version, 0), t.configuration_version, 1)
		where i.template_version is null or i.template_version = 0
	""")
