# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

"""Portable installation configuration for NASECO FieldOps.

Fixtures below are deliberately limited to app-owned reference records. Company,
account, warehouse, user and operational records are configured or created on the
target site and must never be copied from a development database.
"""

import frappe


FIELDOPS_ROLE_NAMES = (
	"Outgrower Supervisor",
	"Outgrower Manager",
	"Quality Inspector",
	"FieldOps Finance Approver",
	"FieldOps Stores User",
	"FieldOps Operations Approver",
)
FIELDOPS_ROLE_PROFILES = (
	"FieldOps Finance",
	"FieldOps Mobile Supervisor",
	"FieldOps Operations Approver",
	"FieldOps Outgrower Manager",
	"FieldOps Quality Inspector",
	"FieldOps Quality Manager",
	"FieldOps Stores",
)
FIELDOPS_WORKFLOW_ACTIONS = (
	"Submit for Department Review",
	"Complete Quality Review",
	"Approve Production Plan",
	"Activate Season Plan",
	"Start Season Closure",
	"Close Season Plan",
	"Cancel Season Plan",
)
CORE_CROPS = ("Maize", "Rice", "Soybean", "Beans", "Groundnuts", "Sunflower")
CORE_VARIETIES = (
	"Hybrid (Generic)",
	"PAN 7351",
	"Red Serenut 4",
	"NASE 14",
	"Maksoy 3N",
	"Maximum",
	"NERICA 4",
	"WITA 9",
	"Longe 7H",
	"Longe 5",
	"Longe 10H",
)
CORE_REGIONS = ("Northern", "Central", "Southern", "Eastern", "Western")
CORE_VISIT_TYPES = (
	"Training Visit",
	"Pest/Disease Check",
	"Harvest Inspection",
	"Pre-Harvest Assessment",
	"Mid-Season Check",
	"Planting Inspection",
	"Emergency Visit",
	"Routine Inspection",
)
CORE_INSPECTION_ATTRIBUTES = (
	"Soil Moisture",
	"Crop Health Score",
	"Expected Yield",
	"Flowering Stage",
	"Weed Pressure",
	"Disease Symptoms",
	"Pest Presence",
	"Leaf Color",
	"Plant Population",
	"Plant Height",
)
CORE_INSPECTION_PARAMETERS = (
	"Number of plants in 5m",
	"Inter row spacing",
	"Plant population per Ha",
	"Male:Female ratio",
	"Isolation distance",
	"Time isolation",
	"Offtypes in females",
	"Offtypes in males",
	"Volunteers",
	"Late maturers",
	"Diseased plants",
	"Noxious weeds",
	"Late detassling",
	"Females shedding pollen",
	"Male line removal",
	"Yield estimate",
)
CORE_INSPECTION_TEMPLATES = (
	"Pre-flowering",
	"1st Flowering",
	"2nd Flowering",
	"3rd Flowering",
	"Pre-harvest",
)
CORE_AGRONOMY_REPORT_TEMPLATES = tuple(
	f"Report {number} - {stage}"
	for number, stage in enumerate(
		(
			"Field Verification & Contracting",
			"Planting",
			"Crop Emergence / Germination",
			"Vegetative",
			"Pre-flowering",
			"Flowering",
			"Pre-harvest",
			"Harvest",
			"Delivery",
		),
		start=1,
	)
)
CORE_AGRONOMY_ACTIVITIES = (
	"Recruit and contract outgrower",
	"Planting",
	"Spraying",
	"Germination check",
	"Scouting for pests",
	"Selective herbicide application",
	"Check herbicide performance",
	"Thinning and removal of offtypes",
	"Urea 40% N 6% S application",
	"Scouting for pests and rouging",
	"Spot manual weeding",
	"Second top dress with Urea 46% N",
	"Prepare field for detassling",
	"Mobilise detassling labour",
	"Detassling starts and labour training",
	"Check field for emerging tassels",
	"Scout for ear rot, smut and termites",
	"Male line removal",
	"Pre-harvest inspection readiness",
	"Harvesting and sorting",
	"Deliver accepted seed harvest",
)
VERSIONED_SEASONS = ("2026 B",)
VERSIONED_PRICING_POLICIES = (
	"2026B Maize Basic Seed Pricing",
	"2026B Maize Certified Seed Pricing",
)
VERSIONED_CONTRACT_TEMPLATES = (
	"2026B Maize Basic Seed Growers Agreement",
	"2026B Maize Certified Seed Growers Agreement",
)


def _named_fixture(doctype, names):
	return {"dt": doctype, "filters": [["name", "in", list(names)]]}


FIXTURES = [
	_named_fixture("Role", FIELDOPS_ROLE_NAMES),
	_named_fixture("Role Profile", FIELDOPS_ROLE_PROFILES),
	_named_fixture("Workflow Action Master", FIELDOPS_WORKFLOW_ACTIONS),
	_named_fixture("Workflow", ("Season Production Plan Approval",)),
	_named_fixture("Region", CORE_REGIONS),
	_named_fixture("Crop", CORE_CROPS),
	_named_fixture("Crop Variety", CORE_VARIETIES),
	_named_fixture("Visit Type", CORE_VISIT_TYPES),
	_named_fixture("Inspection Attribute", CORE_INSPECTION_ATTRIBUTES),
	_named_fixture("Inspection Parameter", CORE_INSPECTION_PARAMETERS),
	_named_fixture("Inspection Template", CORE_INSPECTION_TEMPLATES),
	{
		"dt": "Inspection Standard",
		"filters": [
			["inspection_template", "in", list(CORE_INSPECTION_TEMPLATES)],
			["production_category", "in", ["Basic", "Certified"]],
		],
	},
	_named_fixture("Agronomy Report Template", CORE_AGRONOMY_REPORT_TEMPLATES),
	_named_fixture("Agronomy Activity Template", CORE_AGRONOMY_ACTIVITIES),
	_named_fixture("Crop Recipe", ("Maize Production (Standard)",)),
	_named_fixture("Season", VERSIONED_SEASONS),
	_named_fixture("Outgrower Pricing Policy", VERSIONED_PRICING_POLICIES),
	_named_fixture("Production Contract Template", VERSIONED_CONTRACT_TEMPLATES),
]


TRANSACTIONAL_DOCTYPES = {
	"Agronomy Report",
	"Crop Cycle",
	"Crop Cycle Advance Request",
	"Crop Cycle Settlement",
	"Crop Production Lot",
	"Farm Plot",
	"Field Corrective Action",
	"Inspection",
	"Inspection Take",
	"Outgrower",
	"Outgrower Production Contract",
	"Season Production Plan",
	"Seed Harvest Quality Assessment",
	"Stage Activity",
	"Stage Input Dispatch",
	"Stage Input Request",
}


def configure_site():
	"""Idempotently configure target-site dependencies around portable fixtures."""
	from naseco_fieldopsbackend.fieldops_finance import (
		ensure_crop_cycle_dimensions,
		ensure_erpnext_custom_fields,
		ensure_finance_reference_data,
		setup_outgrower_finance,
	)
	from naseco_fieldopsbackend.patches.configure_fieldops_operating_model import (
		ensure_custom_permissions,
		ensure_production_plan_workflow,
		ensure_role_profiles,
	)
	from naseco_fieldopsbackend.roles import ensure_fieldops_roles
	from naseco_fieldopsbackend.uom import ensure_fieldops_uoms

	ensure_fieldops_roles()
	ensure_fieldops_uoms()
	ensure_finance_reference_data()
	ensure_erpnext_custom_fields()
	ensure_crop_cycle_dimensions()
	ensure_fieldops_settings()
	ensure_role_profiles()
	ensure_custom_permissions()
	ensure_production_plan_workflow()

	# Company/account defaults cannot be fixtures. Populate only from the target site.
	if frappe.db.count("Company"):
		setup_outgrower_finance()
	frappe.clear_cache()


def ensure_fieldops_settings():
	"""Initialize portable QA defaults without replacing target-site settings."""
	settings = frappe.get_single("FieldOps Settings")
	defaults = {
		"target_take_spacing_m": 5,
		"minimum_take_spacing_m": 3,
		"maximum_take_spacing_m": 7,
		"minimum_spacing_compliance_percent": 80,
		"preferred_gps_accuracy_m": 3,
		"maximum_gps_accuracy_m": 5,
		"minimum_location_samples": 3,
		"location_capture_timeout_seconds": 30,
		"maximum_location_age_seconds": 60,
		"allow_positioning_override": 1,
		"positioning_override_role": "System Manager",
	}
	changed = False
	for fieldname, value in defaults.items():
		if settings.get(fieldname) in (None, ""):
			settings.set(fieldname, value)
			changed = True
	if changed:
		settings.save(ignore_permissions=True)


def after_install():
	configure_site()


def after_sync():
	"""Reconcile generated permissions after the first fixture import."""
	configure_site()
	_update_season_statuses()


def after_migrate():
	"""Keep generated ERPNext integration artifacts aligned after upgrades."""
	configure_site()
	_update_season_statuses()


def _update_season_statuses():
	if frappe.db.exists("DocType", "Season"):
		from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season import (
			update_season_statuses,
		)

		update_season_statuses()


def verify_deployment():
	"""Return an installation-readiness report suitable for ``bench execute``."""
	from naseco_fieldopsbackend.fieldops_finance import FIELDOPS_ITEMS
	from naseco_fieldopsbackend.uom import FIELDOPS_UOMS

	missing_fixture_records = {}
	fixture_counts = {}
	for fixture in FIXTURES:
		doctype = fixture["dt"]
		filters = fixture.get("filters")
		count = frappe.db.count(doctype, filters=filters)
		fixture_counts[doctype] = count
		if len(filters or []) == 1 and filters[0][0] == "name" and filters[0][1] == "in":
			expected = set(filters[0][2])
			available = set(frappe.get_all(doctype, filters=filters, pluck="name"))
			if missing := sorted(expected - available):
				missing_fixture_records[doctype] = missing

	required_fields = {
		"Supplier": ("custom_outgrower",),
		"Material Request": ("custom_stage_input_request", "custom_production_contract"),
		"Stock Entry": ("custom_stage_input_request", "custom_production_contract"),
		"Payment Entry": ("custom_crop_cycle_advance_request", "custom_production_contract"),
		"Purchase Receipt Item": ("custom_production_lot",),
		"Purchase Invoice": ("custom_crop_cycle_settlement", "custom_production_contract"),
		"Quality Inspection": ("custom_seed_harvest_quality_assessment",),
	}
	missing_integration_fields = {
		doctype: [fieldname for fieldname in fieldnames if not frappe.get_meta(doctype).has_field(fieldname)]
		for doctype, fieldnames in required_fields.items()
	}
	missing_integration_fields = {
		doctype: fields for doctype, fields in missing_integration_fields.items() if fields
	}
	missing_uoms = sorted(name for name in FIELDOPS_UOMS if not frappe.db.exists("UOM", name))
	missing_items = sorted(
		config["item_code"]
		for config in FIELDOPS_ITEMS.values()
		if not frappe.db.exists("Item", config["item_code"])
	)

	checks = {
		"quality_manager_role": bool(frappe.db.exists("Role", "Quality Manager")),
		"production_plan_workflow": bool(
			frappe.db.exists("Workflow", "Season Production Plan Approval")
		),
		"workspace": bool(frappe.db.exists("Workspace", "NASECO FieldOps")),
		"season_command_centre": bool(frappe.db.exists("Page", "season-command-centre")),
	}
	return {
		"ready": not any(
			(
				missing_fixture_records,
				missing_integration_fields,
				missing_uoms,
				missing_items,
				[check for check, passed in checks.items() if not passed],
			)
		),
		"checks": checks,
		"fixture_counts": fixture_counts,
		"missing_fixture_records": missing_fixture_records,
		"missing_integration_fields": missing_integration_fields,
		"missing_uoms": missing_uoms,
		"missing_items": missing_items,
	}
