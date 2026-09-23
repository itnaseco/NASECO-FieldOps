import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


PARAMETER_CHILD = "Inspection Template Parameter"
APPLICABILITY_CHILD = "Inspection Template Applicability"


def execute():
	_create_parameter_child()
	_create_applicability_child()
	create_custom_fields(
		{
			"Inspection Template": [
				{
					"fieldname": "quality_parameters",
					"label": "Parameters and Standards",
					"fieldtype": "Table",
					"options": PARAMETER_CHILD,
					"insert_after": "effective_to",
				},
				{
					"fieldname": "applicability_rules",
					"label": "Applicability Rules",
					"fieldtype": "Table",
					"options": APPLICABILITY_CHILD,
					"insert_after": "quality_parameters",
				},
			],
			"Inspection Standard": [
				{
					"fieldname": "section_label",
					"label": "Mobile Section",
					"fieldtype": "Data",
					"insert_after": "parameter",
				},
				{
					"fieldname": "display_order",
					"label": "Display Order",
					"fieldtype": "Int",
					"default": "0",
					"insert_after": "section_label",
				},
			],
		},
		update=True,
	)
	# Global template standards are valid; category-specific rows still take
	# precedence in the scheduler and Inspection controller.
	make_property_setter(
		"Inspection Standard", "production_category", "reqd", 0, "Check"
	)
	frappe.db.sql(
		"""
		update `tabInspection Template`
		set lifecycle_status = 'Published',
			configuration_version = coalesce(nullif(configuration_version, 0), 1)
		where active = 1 and ifnull(lifecycle_status, '') = ''
		"""
	)
	frappe.db.sql(
		"""
		update `tabInspection Template`
		set configuration_version = 1
		where configuration_version is null or configuration_version = 0
		"""
	)
	_backfill_parameter_rows()


def _create_parameter_child():
	if frappe.db.exists("DocType", PARAMETER_CHILD):
		return
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": PARAMETER_CHILD,
			"module": "Naseco FieldOpsBackend",
			"custom": 1,
			"istable": 1,
			"editable_grid": 1,
			"fields": [
				{"fieldname": "parameter", "label": "Parameter", "fieldtype": "Link", "options": "Inspection Parameter", "reqd": 1, "in_list_view": 1},
				{"fieldname": "inspection_attribute", "label": "Attribute", "fieldtype": "Link", "options": "Inspection Attribute", "fetch_from": "parameter.inspection_attribute", "read_only": 1},
				{"fieldname": "section_label", "label": "Mobile Section", "fieldtype": "Data", "in_list_view": 1},
				{"fieldname": "display_order", "label": "Display Order", "fieldtype": "Int", "default": "0", "in_list_view": 1},
				{"fieldname": "production_category", "label": "Production Category", "fieldtype": "Link", "options": "Seed Category"},
				{"fieldname": "seed_class", "label": "Seed Class", "fieldtype": "Link", "options": "Seed Class"},
				{"fieldname": "mandatory", "label": "Mandatory", "fieldtype": "Check", "default": "1", "in_list_view": 1},
				{"fieldname": "comparison_rule", "label": "Comparison Rule", "fieldtype": "Select", "options": "At Least\nAt Most\nBetween\nEquals\nYes Is Pass\nNo Is Pass\nIsolation Distance", "reqd": 1},
				{"fieldname": "minimum_value", "label": "Minimum Value", "fieldtype": "Float"},
				{"fieldname": "maximum_value", "label": "Maximum Value", "fieldtype": "Float"},
				{"fieldname": "expected_text", "label": "Expected Text", "fieldtype": "Data"},
				{"fieldname": "unit", "label": "Unit", "fieldtype": "Link", "options": "UOM"},
				{"fieldname": "good_label", "label": "Pass Label", "fieldtype": "Data", "default": "Good"},
				{"fieldname": "poor_label", "label": "Fail Label", "fieldtype": "Data", "default": "Poor"},
				{"fieldname": "aggregation_method", "label": "Aggregation", "fieldtype": "Select", "options": "Worst Case\nAverage\nMinimum\nMaximum\nSum\nAll Must Pass\nCumulative Incidence", "default": "Worst Case", "reqd": 1},
				{"fieldname": "auto_reject_on_fail", "label": "Auto Reject on Fail", "fieldtype": "Check", "default": "0"},
				{"fieldname": "corrective_action_on_fail", "label": "Corrective Action on Fail", "fieldtype": "Check", "default": "1"},
				{"fieldname": "standard_notes", "label": "Instructions / Standard Notes", "fieldtype": "Text"},
				{"fieldname": "active", "label": "Active", "fieldtype": "Check", "default": "1", "in_list_view": 1},
			],
		}
	).insert(ignore_permissions=True)


def _create_applicability_child():
	if frappe.db.exists("DocType", APPLICABILITY_CHILD):
		return
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": APPLICABILITY_CHILD,
			"module": "Naseco FieldOpsBackend",
			"custom": 1,
			"istable": 1,
			"editable_grid": 1,
			"fields": [
				{"fieldname": "crop", "label": "Crop", "fieldtype": "Link", "options": "Crop", "in_list_view": 1},
				{"fieldname": "variety", "label": "Variety", "fieldtype": "Link", "options": "Variety"},
				{"fieldname": "production_category", "label": "Production Category", "fieldtype": "Link", "options": "Seed Category"},
				{"fieldname": "seed_class", "label": "Seed Class", "fieldtype": "Link", "options": "Seed Class"},
				{"fieldname": "region", "label": "Region", "fieldtype": "Link", "options": "Region", "in_list_view": 1},
				{"fieldname": "season", "label": "Season", "fieldtype": "Link", "options": "Season"},
				{"fieldname": "outgrower", "label": "Outgrower", "fieldtype": "Link", "options": "Outgrower"},
				{"fieldname": "plot", "label": "Farm Plot", "fieldtype": "Link", "options": "Farm Plot"},
				{"fieldname": "effective_from", "label": "Effective From", "fieldtype": "Date"},
				{"fieldname": "effective_to", "label": "Effective To", "fieldtype": "Date"},
				{"fieldname": "priority", "label": "Priority", "fieldtype": "Int", "default": "0", "in_list_view": 1},
				{"fieldname": "active", "label": "Active", "fieldtype": "Check", "default": "1", "in_list_view": 1},
			],
		}
	).insert(ignore_permissions=True)


def _backfill_parameter_rows():
	for template in frappe.get_all("Inspection Template", pluck="name"):
		if frappe.db.exists(PARAMETER_CHILD, {"parent": template, "parentfield": "quality_parameters"}):
			continue
		standards = frappe.get_all(
			"Inspection Standard",
			filters={"inspection_template": template},
			fields=["*"],
			order_by="creation asc, parameter asc",
		)
		for index, standard in enumerate(standards, 1):
			attribute = frappe.db.get_value("Inspection Parameter", standard.parameter, "inspection_attribute")
			frappe.get_doc(
				{
					"doctype": PARAMETER_CHILD,
					"parent": template,
					"parenttype": "Inspection Template",
					"parentfield": "quality_parameters",
					"idx": index,
					"parameter": standard.parameter,
					"inspection_attribute": attribute,
					"section_label": standard.get("section_label"),
					"display_order": standard.get("display_order") or index,
					"production_category": standard.production_category,
					"seed_class": standard.seed_class,
					"mandatory": standard.mandatory,
					"comparison_rule": standard.comparison_rule,
					"minimum_value": standard.minimum_value,
					"maximum_value": standard.maximum_value,
					"expected_text": standard.expected_text,
					"unit": standard.unit,
					"good_label": standard.good_label,
					"poor_label": standard.poor_label,
					"aggregation_method": standard.aggregation_method,
					"auto_reject_on_fail": standard.auto_reject_on_fail,
					"corrective_action_on_fail": standard.corrective_action_on_fail,
					"standard_notes": standard.standard_notes,
					"active": 1,
				}
			).insert(ignore_permissions=True)
