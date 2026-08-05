# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, cint

from naseco_fieldopsbackend.fieldops_finance import (
	FIELDOPS_ITEMS,
	ensure_finance_reference_data,
	ensure_outgrower_supplier,
)
from naseco_fieldopsbackend.roles import ensure_fieldops_roles
from naseco_fieldopsbackend.uom import ensure_fieldops_uoms


def execute(include_demo=0):
	"""Seed FieldOps reference data; operational demo records are opt-in."""
	print("\n" + "="*60)
	print("Seeding Reference Data for NASECO FieldOps")
	print("="*60 + "\n")

	# Seed in correct order (respecting dependencies)
	try:
		seed_regions()
		seed_fieldops_roles()
		seed_uoms()
		seed_fieldops_settings()
		seed_finance_reference_data()
		seed_crops()
		seed_varieties()
		seed_seasons()
		seed_26b_contract_reference_data()
		seed_visit_types()
		seed_inspection_attributes()
		seed_inspection_parameters()
		seed_inspection_templates()
		seed_inspection_standards()
		seed_agronomy_report_templates()
		seed_agronomy_activity_templates()
		if cint(include_demo):
			seed_sample_season_production_plan()
			seed_sample_fieldops_data()

		print("\n" + "="*60)
		print("Seeding Completed Successfully!")
		print("="*60 + "\n")
	except Exception as e:
		print(f"\n✗ Seeding failed: {str(e)}")
		frappe.db.rollback()
		raise


def execute_demo():
	"""Explicitly install the non-production sample plan, farmer and field records."""
	execute(include_demo=1)


def seed_regions():
	"""Create regions"""
	print("Creating Regions...")
	regions = [
		{"region_name": "Northern"},
		{"region_name": "Central"},
		{"region_name": "Southern"},
		{"region_name": "Eastern"},
		{"region_name": "Western"}
	]

	for region_data in regions:
		try:
			if not frappe.db.exists("Region", region_data["region_name"]):
				doc = frappe.get_doc({
					"doctype": "Region",
					**region_data
				})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				print(f"  ✓ Created Region: {region_data['region_name']}")
			else:
				print(f"  → Region already exists: {region_data['region_name']}")
		except Exception as e:
			print(f"  ✗ Error creating Region {region_data['region_name']}: {str(e)}")
			frappe.db.rollback()


def seed_fieldops_roles():
	"""Create the operational roles required by FieldOps workflows."""
	print("\nCreating FieldOps Roles...")
	ensure_fieldops_roles()
	frappe.db.commit()
	print("  ✓ Outgrower Supervisor role ready")


def seed_uoms():
	"""Create the standard ERPNext UOM records used by FieldOps."""
	print("\nCreating UOMs...")
	ensure_fieldops_uoms()
	frappe.db.commit()
	print("  ✓ FieldOps UOMs ready")


def seed_fieldops_settings():
	"""Initialize QA positioning standards without overwriting configured values."""
	print("\nCreating FieldOps Settings...")
	configured = frappe.db.sql(
		"select value from tabSingles where doctype = %s and field = %s",
		("FieldOps Settings", "target_take_spacing_m"),
	)
	if configured:
		print("  → FieldOps Settings already configured")
		return

	settings = frappe.get_doc("FieldOps Settings")
	settings.update(
		{
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
	)
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	print("  ✓ FieldOps positioning standards configured")


def seed_finance_reference_data():
	print("\nCreating FieldOps Items...")
	ensure_finance_reference_data()
	frappe.db.commit()
	print("  ✓ Agricultural input and harvest Items ready")


def seed_crops():
	"""Create crops"""
	print("\nCreating Crops...")
	crops = [
		{"crop_name": "Maize"},
		{"crop_name": "Rice"},
		{"crop_name": "Soybean"},
		{"crop_name": "Beans"},
		{"crop_name": "Groundnuts"},
		{"crop_name": "Sunflower"}
	]

	for crop_data in crops:
		try:
			if not frappe.db.exists("Crop", crop_data["crop_name"]):
				doc = frappe.get_doc({
					"doctype": "Crop",
					**crop_data
				})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				print(f"  ✓ Created Crop: {crop_data['crop_name']}")
			else:
				print(f"  → Crop already exists: {crop_data['crop_name']}")
		except Exception as e:
			print(f"  ✗ Error creating Crop {crop_data['crop_name']}: {str(e)}")
			frappe.db.rollback()


def seed_varieties():
	"""Create crop varieties"""
	print("\nCreating Crop Varieties...")
	varieties = [
		{"variety_name": "Longe 10H", "crop": "Maize", "maturity_days": 120},
		{"variety_name": "Longe 5", "crop": "Maize", "maturity_days": 100},
		{"variety_name": "Longe 7H", "crop": "Maize", "maturity_days": 110},
		{"variety_name": "WITA 9", "crop": "Rice", "maturity_days": 120},
		{"variety_name": "NERICA 4", "crop": "Rice", "maturity_days": 110},
		{"variety_name": "Maximum", "crop": "Soybean", "maturity_days": 100},
		{"variety_name": "Maksoy 3N", "crop": "Soybean", "maturity_days": 95},
		{"variety_name": "NASE 14", "crop": "Beans", "maturity_days": 75},
		{"variety_name": "Red Serenut 4", "crop": "Groundnuts", "maturity_days": 105},
		{"variety_name": "PAN 7351", "crop": "Sunflower", "maturity_days": 90}
	]

	for variety_data in varieties:
		variety_name = variety_data["variety_name"]
		try:
			if not frappe.db.exists("Crop Variety", variety_name):
				# Verify the crop exists first
				if not frappe.db.exists("Crop", variety_data["crop"]):
					print(f"  ✗ Cannot create variety {variety_name}: Crop '{variety_data['crop']}' does not exist")
					continue

				doc = frappe.get_doc({
					"doctype": "Crop Variety",
					**variety_data
				})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				print(f"  ✓ Created Variety: {variety_name} ({variety_data['crop']})")
			else:
				print(f"  → Variety already exists: {variety_name}")
		except Exception as e:
			print(f"  ✗ Error creating Variety {variety_name}: {str(e)}")
			frappe.db.rollback()


def seed_seasons():
	"""Create seasons"""
	print("\nCreating Seasons...")
	seasons = [
		{"season_name": "Season A 2024", "start_date": "2024-03-01", "end_date": "2024-08-31"},
		{"season_name": "Season B 2024", "start_date": "2024-09-01", "end_date": "2025-02-28"},
		{"season_name": "Season A 2025", "start_date": "2025-03-01", "end_date": "2025-08-31"},
		{"season_name": "Season B 2025", "start_date": "2025-09-01", "end_date": "2026-02-28"},
		{"season_name": "Season A 2026", "start_date": "2026-03-01", "end_date": "2026-07-14"},
		{"season_name": "2026 B", "start_date": "2026-07-15", "end_date": "2027-01-31"},
	]

	for season_data in seasons:
		season_name = season_data["season_name"]
		try:
			if not frappe.db.exists("Season", season_name):
				doc = frappe.get_doc({
					"doctype": "Season",
					**season_data
				})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				print(f"  ✓ Created Season: {season_name}")
			else:
				frappe.db.set_value(
					"Season",
					season_name,
					{
						"start_date": season_data["start_date"],
						"end_date": season_data["end_date"],
					},
				)
				print(f"  → Season already exists: {season_name}")
		except Exception as e:
			print(f"  ✗ Error creating Season {season_name}: {str(e)}")
			frappe.db.rollback()


def seed_26b_contract_reference_data():
	"""Create the approved, versioned reference records extracted from the 26B agreement."""
	print("\nCreating 26B Contract Policies and Templates...")
	if not (
		frappe.db.exists("Season", "2026 B")
		and frappe.db.exists("Crop", "Maize")
		and frappe.db.exists("Item", "FO-MAIZE-GRAIN")
	):
		print("  -> 26B prerequisites are not available")
		return

	for category in ("Basic", "Certified"):
		policy_name = f"2026B Maize {category} Seed Pricing"
		if not frappe.db.exists("Outgrower Pricing Policy", policy_name):
			policy = frappe.get_doc(
				{
					"doctype": "Outgrower Pricing Policy",
					"policy_name": policy_name,
					"policy_version": "26B.1",
					"season": "2026 B",
					"crop": "Maize",
					"production_category": category,
					"currency": "UGX",
					"effective_from": "2026-07-15",
					"effective_to": "2027-01-31",
					"quota_kg_per_acre": 1000,
					"minimum_seed_yield_kg_per_acre": 800,
					"excess_rate_per_kg": 1600,
					"grain_item": "FO-MAIZE-GRAIN",
					"grain_rate_per_kg": FIELDOPS_ITEMS["Maize Grain"]["rate"],
					"advance_valuation_rate": 1600,
					"moisture_target_percent": 13,
					"minimum_germination_percent": 95,
					"screen_size_mm": 8,
					"undersize_threshold_percent": 5,
					"screen_weight_deduction_percent": 5,
					"reject_threshold_percent": 1,
					"reject_value_deduction_percent": 5,
					"high_bonus_purity_threshold": 95,
					"high_bonus_rate_per_kg": 100,
					"standard_bonus_purity_threshold": 85,
					"standard_bonus_rate_per_kg": 50,
					"bonus_payment_days": 150,
					"bonus_requires_approval": 1,
					"payment_due_days": 75,
					"late_interest_percent_per_month": 1,
					"collection_due_days": 30,
					"blacklist_purity_threshold": 85,
					"blacklist_consecutive_seasons": 2,
					"resolution_notes": (
						"<p>The upper boundary is exclusive: 98% and above uses the "
						"highest purity band. Yield below 800 kg/acre, purity below "
						"90%, or germination below 95% uses the approved grain rate. "
						"The UGX 1,200 grain rate is sample reference data and must be "
						"reviewed against the authorized market rate before production "
						"settlement.</p>"
					),
					"pricing_bands": get_26b_pricing_bands(),
				}
			)
			policy.insert(ignore_permissions=True)
			policy.submit()
			print(f"  + Created pricing policy: {policy_name}")
		else:
			print(f"  -> Pricing policy already exists: {policy_name}")

		template_name = f"2026B Maize {category} Seed Growers Agreement"
		if not frappe.db.exists("Production Contract Template", template_name):
			template = frappe.get_doc(
				{
					"doctype": "Production Contract Template",
					"template_name": template_name,
					"template_version": "26B.1",
					"season": "2026 B",
					"crop": "Maize",
					"production_category": category,
					"pricing_policy": policy_name,
					"effective_from": "2026-07-15",
					"effective_to": "2027-01-31",
					"agreement_title": "Out Growers Agreement for Seed Production - 26B",
					"seed_handbook_reference": "NASECO Seed Production Handbook",
					"legal_reference": (
						"Applicable Uganda seed law and National Seed Certification "
						"Service inspection and certification requirements."
					),
					"company_responsibilities": (
						"<ol><li>Provide approved parent seed and agreed crop inputs.</li>"
						"<li>Provide technical supervision, field inspection coordination "
						"and harvest collection.</li><li>Collect crib-ready seed within "
						"30 days and pay accepted seed within 75 days.</li></ol>"
					),
					"farmer_responsibilities": (
						"<ol><li>Maintain the contracted acreage, a minimum 200 metre "
						"isolation distance and the approved five-day planting lot.</li>"
						"<li>Follow the crop recipe, agronomy instructions and field "
						"inspection corrective actions.</li><li>Deliver dry, traceable "
						"seed and protect company-supplied parent seed and inputs.</li></ol>"
					),
					"supervisor_responsibilities": (
						"<ol><li>Verify plot, isolation, planting lot and stage records.</li>"
						"<li>Schedule and document agronomy activities and corrective "
						"actions.</li><li>Maintain traceability through harvest, crib "
						"readiness, collection and delivery.</li></ol>"
					),
					"quality_terms": (
						"<p>Initial payment uses net dry quantity normalized to 13% "
						"moisture, minimum 95% germination, genetic-purity/yield bands, "
						"an 8 mm screen rule and reject penalties. Potential genetic "
						"purity bonuses are deferred for QA approval and are due within "
						"150 days. NSCS or approved laboratory evidence is required.</p>"
					),
					"input_recovery_terms": (
						"<p>Approved parent seed, stock inputs and supplier cash advances "
						"are recorded against the Crop Cycle and recovered transparently "
						"from the accepted harvest settlement.</p>"
					),
					"termination_terms": (
						"<p>Company parent seed remains company property. Rejected or "
						"decertified acreage and produce are handled under the agreement "
						"and certification decision. Purity below 85% in two consecutive "
						"seasons triggers an eligibility review before a new contract.</p>"
					),
				}
			)
			template.insert(ignore_permissions=True)
			template.submit()
			print(f"  + Created contract template: {template_name}")
		else:
			print(f"  -> Contract template already exists: {template_name}")
	frappe.db.commit()


def get_26b_pricing_bands():
	bands = [
		("Below Minimum Yield", 0, 800, 0, 0, "Grain Price", 0),
	]
	for label, minimum_yield, maximum_yield, rates in (
		("800-999 kg/acre", 800, 1000, ((98, 0, 1850), (95, 98, 1700), (90, 95, 1600))),
		("1000+ kg/acre", 1000, 0, ((98, 0, 2100), (95, 98, 2000), (90, 95, 1850))),
	):
		for minimum_purity, maximum_purity, rate in rates:
			bands.append(
				(
					f"{label}; purity {minimum_purity}+",
					minimum_yield,
					maximum_yield,
					minimum_purity,
					maximum_purity,
					"Fixed Rate",
					rate,
				)
			)
		bands.append(
			(
				f"{label}; purity below 90%",
				minimum_yield,
				maximum_yield,
				0,
				90,
				"Grain Price",
				0,
			)
		)
	return [
		{
			"band_name": name,
			"minimum_yield_kg_per_acre": min_yield,
			"maximum_yield_kg_per_acre": max_yield,
			"minimum_purity_percent": min_purity,
			"maximum_purity_percent": max_purity,
			"price_basis": basis,
			"rate_per_kg": rate,
		}
		for name, min_yield, max_yield, min_purity, max_purity, basis, rate in bands
	]


def seed_visit_types():
	"""Create visit types"""
	print("\nCreating Visit Types...")
	visit_types = [
		{"type_name": "Routine Inspection"},
		{"type_name": "Emergency Visit"},
		{"type_name": "Planting Inspection"},
		{"type_name": "Mid-Season Check"},
		{"type_name": "Pre-Harvest Assessment"},
		{"type_name": "Harvest Inspection"},
		{"type_name": "Pest/Disease Check"},
		{"type_name": "Training Visit"}
	]

	for vt_data in visit_types:
		type_name = vt_data["type_name"]
		try:
			if not frappe.db.exists("Visit Type", type_name):
				doc = frappe.get_doc({
					"doctype": "Visit Type",
					**vt_data
				})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				print(f"  ✓ Created Visit Type: {type_name}")
			else:
				print(f"  → Visit Type already exists: {type_name}")
		except Exception as e:
			print(f"  ✗ Error creating Visit Type {type_name}: {str(e)}")
			frappe.db.rollback()


def seed_inspection_attributes():
	"""Create inspection attributes"""
	print("\nCreating Inspection Attributes...")
	attributes = [
		{"attribute_name": "Plant Height", "attribute_type": "Numeric", "unit": "Centimeter"},
		{"attribute_name": "Plant Population", "attribute_type": "Numeric", "unit": "Nos"},
		{"attribute_name": "Leaf Color", "attribute_type": "Text"},
		{"attribute_name": "Pest Presence", "attribute_type": "Boolean"},
		{"attribute_name": "Disease Symptoms", "attribute_type": "Text"},
		{"attribute_name": "Soil Moisture", "attribute_type": "Text"},
		{"attribute_name": "Weed Pressure", "attribute_type": "Text"},
		{"attribute_name": "Flowering Stage", "attribute_type": "Boolean"},
		{"attribute_name": "Expected Yield", "attribute_type": "Numeric", "unit": "Kg"},
		{"attribute_name": "Crop Health Score", "attribute_type": "Numeric"}
	]

	for attr_data in attributes:
		attr_name = attr_data["attribute_name"]
		try:
			if not frappe.db.exists("Inspection Attribute", attr_name):
				doc = frappe.get_doc({
					"doctype": "Inspection Attribute",
					**attr_data
				})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				print(f"  ✓ Created Attribute: {attr_name}")
			else:
				print(f"  → Attribute already exists: {attr_name}")
		except Exception as e:
			print(f"  ✗ Error creating Attribute {attr_name}: {str(e)}")
			frappe.db.rollback()


def seed_inspection_parameters():
	"""Create QA parameters used by stage inspections."""
	print("\nCreating Inspection Parameters...")
	parameters = [
		("Number of plants in 5m", "PLANTS_5M", "Planting", "Number", "Nos", "Farmer", 1),
		("Inter row spacing", "INTER_ROW_SPACING", "Planting", "Number", "Meter", "Outgrower Supervisor", 0),
		("Plant population per Ha", "PLANT_POP_HA", "Planting", "Number", "Nos", "Both", 0),
		("Male:Female ratio", "MALE_FEMALE_RATIO", "Planting", "Ratio", None, "Outgrower Supervisor", 0),
		("Isolation distance", "ISOLATION_DISTANCE", "Isolation", "Number", "Meter", "Outgrower Supervisor", 0),
		("Time isolation", "TIME_ISOLATION", "Isolation", "Number", "Week", "Outgrower Supervisor", 0),
		("Offtypes in females", "OFFTYPES_FEMALE", "Purity", "Count", "Nos", "Both", 1),
		("Offtypes in males", "OFFTYPES_MALE", "Purity", "Count", "Nos", "Both", 1),
		("Volunteers", "VOLUNTEERS", "Purity", "Count", "Nos", "Farmer", 1),
		("Late maturers", "LATE_MATURERS", "Purity", "Count", "Nos", "Both", 1),
		("Diseased plants", "DISEASED_PLANTS", "Disease", "Count", "Nos", "Farmer", 1),
		("Noxious weeds", "NOXIOUS_WEEDS", "Weed", "Count", "Nos", "Farmer", 1),
		("Late detassling", "LATE_DETASSLING", "Detassling", "Yes/No", None, "Outgrower Supervisor", 0),
		("Females shedding pollen", "FEMALES_SHEDDING_POLLEN", "Detassling", "Count", "Nos", "Outgrower Supervisor", 1),
		("Male line removal", "MALE_LINE_REMOVAL", "Harvest", "Yes/No", None, "Farmer", 0),
		("Yield estimate", "YIELD_ESTIMATE", "Harvest", "Number", "Kg", "Farmer", 0),
	]

	for name, code, group, data_type, unit, applies_to, requires_counts in parameters:
		measurement_scope = "Inspection" if code in ("ISOLATION_DISTANCE", "TIME_ISOLATION") else "Inspection Take"
		calculation_method = "Cumulative Incidence" if requires_counts else "Direct Value"
		values = {
			"parameter_code": code,
			"parameter_group": group,
			"data_type": data_type,
			"unit": unit,
			"applies_to": applies_to,
			"measurement_scope": measurement_scope,
			"calculation_method": calculation_method,
			"denominator_basis": "Total Plants Counted" if requires_counts else None,
			"requires_take_counts": requires_counts,
		}
		if frappe.db.exists("Inspection Parameter", name):
			frappe.db.set_value(
				"Inspection Parameter", name, values, update_modified=False
			)
			print(f"  → Parameter already exists: {name}")
			continue
		doc = frappe.get_doc({
			"doctype": "Inspection Parameter",
			"parameter_name": name,
			**values,
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		print(f"  ✓ Created Parameter: {name}")


def seed_inspection_templates():
	"""Create QA inspection templates from the revised QA survey."""
	print("\nCreating Inspection Templates...")
	templates = [
		("Pre-flowering", "Pre-flowering", "Vegetative Growth & Initiation", 45, 45),
		("1st Flowering", "1st Flowering", "Tassel Visible to Silking", 60, 60),
		("2nd Flowering", "2nd Flowering", "Female Flowering", 63, 63),
		("3rd Flowering", "3rd Flowering", "Female Flowering", 66, 66),
		("Pre-harvest", "Pre-harvest", "Physiological Maturity", 105, 180),
	]
	for name, inspection_type, crop_stage, due_start, due_end in templates:
		if frappe.db.exists("Inspection Template", name):
			print(f"  → Template already exists: {name}")
			continue
		doc = frappe.get_doc({
			"doctype": "Inspection Template",
			"template_name": name,
			"inspection_type": inspection_type,
			"crop_stage": crop_stage,
			"due_days_from_planting": due_start,
			"due_window_end_days": due_end,
			"counts_per_hectare": 4,
			"active": 1,
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		print(f"  ✓ Created Template: {name}")


def seed_inspection_standards():
	"""Create Basic/Certified QA standards used by automatic compliance checks."""
	print("\nCreating Inspection Standards...")
	all_flowering = ["Pre-flowering", "1st Flowering", "2nd Flowering", "3rd Flowering"]
	standard_rows = []
	cumulative_parameters = {
		"Offtypes in females",
		"Offtypes in males",
		"Volunteers",
		"Late maturers",
		"Diseased plants",
		"Noxious weeds",
		"Females shedding pollen",
	}

	for template in all_flowering:
		standard_rows.extend([
			(template, "Isolation distance", "Basic", "Isolation Distance", 400, None, None, 1, 0),
			(template, "Isolation distance", "Certified", "Isolation Distance", 200, None, None, 1, 0),
			(template, "Time isolation", "Basic", "At Least", 6, None, None, 1, 0),
			(template, "Time isolation", "Certified", "At Least", 5, None, None, 1, 0),
			(template, "Offtypes in females", "Basic", "At Most", None, 0.05, None, 1, 0),
			(template, "Offtypes in females", "Certified", "At Most", None, 0.1, None, 1, 0),
			(template, "Offtypes in males", "Basic", "At Most", None, 0.05, None, 1, 1),
			(template, "Offtypes in males", "Certified", "At Most", None, 0.1, None, 1, 1),
			(template, "Volunteers", "Basic", "At Most", None, 0.05, None, 0, 0),
			(template, "Volunteers", "Certified", "At Most", None, 0.1, None, 0, 0),
			(template, "Late maturers", "Basic", "At Most", None, 0.05, None, 1, 0),
			(template, "Late maturers", "Certified", "At Most", None, 0.1, None, 1, 0),
			(template, "Diseased plants", "Basic", "At Most", None, 0, None, 1, 1),
			(template, "Diseased plants", "Certified", "At Most", None, 0, None, 1, 1),
			(template, "Noxious weeds", "Basic", "At Most", None, 0.1, None, 1, 0),
			(template, "Noxious weeds", "Certified", "At Most", None, 0.1, None, 1, 0),
		])

	for template in ["1st Flowering", "2nd Flowering", "3rd Flowering"]:
		standard_rows.extend([
			(template, "Late detassling", "Basic", "No Is Pass", None, None, "No", 1, 1),
			(template, "Late detassling", "Certified", "No Is Pass", None, None, "No", 1, 1),
			(template, "Females shedding pollen", "Basic", "At Most", None, 0.2, None, 1, 1),
			(template, "Females shedding pollen", "Certified", "At Most", None, 0.005, None, 1, 1),
		])

	standard_rows.extend([
		("Pre-harvest", "Male line removal", "Basic", "Yes Is Pass", None, None, "Yes", 1, 1),
		("Pre-harvest", "Male line removal", "Certified", "Yes Is Pass", None, None, "Yes", 1, 1),
		("Pre-harvest", "Diseased plants", "Basic", "At Most", None, 0, None, 1, 1),
		("Pre-harvest", "Diseased plants", "Certified", "At Most", None, 0, None, 1, 1),
		("Pre-harvest", "Noxious weeds", "Basic", "At Most", None, 0.1, None, 1, 0),
		("Pre-harvest", "Noxious weeds", "Certified", "At Most", None, 0.1, None, 1, 0),
	])

	for template, parameter, category, rule, min_value, max_value, expected, mandatory, auto_reject in standard_rows:
		aggregation_method = (
			"Cumulative Incidence"
			if parameter in cumulative_parameters
			else
			"Minimum"
			if rule in ("At Least", "Isolation Distance")
			else "Maximum"
			if rule == "At Most"
			else "All Must Pass"
		)
		existing_standard = frappe.db.get_value("Inspection Standard", {
			"inspection_template": template,
			"parameter": parameter,
			"production_category": category,
		})
		if existing_standard:
			values = {"aggregation_method": aggregation_method}
			if parameter in cumulative_parameters:
				values["unit"] = "Nos"
			frappe.db.set_value(
				"Inspection Standard",
				existing_standard,
				values,
				update_modified=False,
			)
			continue
		doc = frappe.get_doc({
			"doctype": "Inspection Standard",
			"inspection_template": template,
			"parameter": parameter,
			"production_category": category,
			"mandatory": mandatory,
			"comparison_rule": rule,
			"aggregation_method": aggregation_method,
			"unit": "Nos" if parameter in cumulative_parameters else None,
			"minimum_value": min_value,
			"maximum_value": max_value,
			"expected_text": expected,
			"good_label": "Good",
			"poor_label": "Poor",
			"auto_reject_on_fail": auto_reject,
			"corrective_action_on_fail": 1,
		})
		doc.insert(ignore_permissions=True)
	print("  ✓ Inspection Standards seeded")
	frappe.db.commit()


def seed_agronomy_report_templates():
	"""Create the nine structured supervisor reports defined by the field workbook."""
	print("\nCreating Agronomy Report Templates...")
	automated_rules = {
		"CONTRACT_CONFIRMED": ("Yes Is Pass", None, None, None),
		"FIELD_OWNERSHIP": ("Yes Is Pass", None, None, None),
		"LAND_PREPARATION": ("Good Is Pass", None, None, None),
		"ISOLATION_QUALITY": ("Good Is Pass", None, None, None),
		"BASAL_FERTILIZER": ("Yes Is Pass", None, None, None),
		"GERMINATION_PERCENT": ("At Least", 80, None, None),
		"STAND_UNIFORMITY": ("Good Is Pass", None, None, None),
		"GAP_FILLING": ("No Is Pass", None, None, None),
		"EARLY_PESTS": ("Good Is Pass", None, None, None),
		"WEED_STATUS": ("Good Is Pass", None, None, None),
		"CROP_VIGOUR": ("Good Is Pass", None, None, None),
		"THINNING_COMPLETE": ("Yes Is Pass", None, None, None),
		"OFFTYPES_ROUGED": ("Yes Is Pass", None, None, None),
		"PEST_DISEASE_STATUS": ("Good Is Pass", None, None, None),
		"TOPDRESS_APPLIED": ("Yes Is Pass", None, None, None),
		"WEED_CONTROL": ("Good Is Pass", None, None, None),
		"CROP_UNIFORMITY": ("Good Is Pass", None, None, None),
		"OFFTYPES_STATUS": ("Good Is Pass", None, None, None),
		"SECOND_TOPDRESS": ("Yes Is Pass", None, None, None),
		"DETASSEL_READINESS": ("Good Is Pass", None, None, None),
		"LABOUR_READY": ("Yes Is Pass", None, None, None),
		"DETASSEL_STATUS": ("Good Is Pass", None, None, None),
		"FEMALE_POLLEN_SHEDDING": ("Good Is Pass", None, None, None),
		"DISEASE_STATUS": ("Good Is Pass", None, None, None),
		"MALE_LINE_REMOVED": ("Yes Is Pass", None, None, None),
		"FIELD_PURITY": ("Good Is Pass", None, None, None),
		"EAR_DISEASE_STATUS": ("Good Is Pass", None, None, None),
		"SORTING_STATUS": ("Good Is Pass", None, None, None),
		"DELIVERY_MOISTURE": ("At Most", None, 13.5, None),
	}
	critical_parameters = {
		"ISOLATION_QUALITY",
		"OFFTYPES_ROUGED",
		"OFFTYPES_STATUS",
		"DETASSEL_STATUS",
		"FEMALE_POLLEN_SHEDDING",
		"MALE_LINE_REMOVED",
		"FIELD_PURITY",
	}
	failure_actions = {
		"ISOLATION_QUALITY": "Escalate the isolation breach and restore the approved isolation control before the next stage.",
		"GERMINATION_PERCENT": "Assess the failed stand and complete the approved gap-filling or replanting action.",
		"OFFTYPES_ROUGED": "Complete roguing of all identified off-types and attach completion evidence.",
		"OFFTYPES_STATUS": "Remove all identified off-types before the next field review.",
		"DETASSEL_STATUS": "Complete corrective detasselling immediately and record the affected area.",
		"FEMALE_POLLEN_SHEDDING": "Remove affected female plants and escalate the seed-purity risk for review.",
		"MALE_LINE_REMOVED": "Remove the male line before harvesting the female seed crop.",
		"FIELD_PURITY": "Complete the prescribed purity correction and request field verification.",
		"DELIVERY_MOISTURE": "Dry and condition the delivered seed to 13.5 percent moisture or below.",
	}
	reports = [
		(1, "Field Verification & Contracting", -30, -1, [
			("CONTRACT_CONFIRMED", "Production contract confirmed", "Contract", "Yes/No", None, 1, 1),
			("FIELD_OWNERSHIP", "Field ownership / access verified", "Field", "Yes/No", None, 1, 1),
			("FIELD_AREA", "Verified field area", "Field", "Number", "Acre", 1, 0),
			("PREVIOUS_CROP", "Previous crop", "Field", "Data", None, 1, 0),
			("LAND_PREPARATION", "Land preparation status", "Field", "Good/Poor", None, 1, 1),
			("ISOLATION_QUALITY", "Isolation distance quality", "Seed Quality", "Good/Poor", None, 1, 1),
			("SEED_CATEGORY", "Seed production category", "Seed Quality", "Select", None, 1, 0),
		]),
		(2, "Planting", 0, 0, [
			("PLANTING_DATE", "Actual planting date", "Planting", "Date", None, 1, 0),
			("PLANTED_AREA", "Area planted", "Planting", "Number", "Acre", 1, 0),
			("SEED_QUANTITY", "Seed quantity used", "Inputs", "Number", "Kg", 1, 0),
			("MALE_FEMALE_RATIO", "Male to female row ratio", "Planting", "Data", None, 1, 1),
			("PLANTING_METHOD", "Planting method", "Planting", "Data", None, 1, 0),
			("BASAL_FERTILIZER", "Basal fertilizer applied", "Inputs", "Yes/No", None, 1, 1),
		]),
		(3, "Crop Emergence / Germination", 7, 14, [
			("GERMINATION_PERCENT", "Germination percentage", "Crop Establishment", "Percent", "Percent", 1, 1),
			("STAND_UNIFORMITY", "Crop stand uniformity", "Crop Establishment", "Good/Poor", None, 1, 1),
			("GAP_FILLING", "Gap filling required", "Corrective Work", "Yes/No", None, 1, 1),
			("EARLY_PESTS", "Early pest incidence", "Crop Health", "Good/Poor", None, 1, 1),
			("WEED_STATUS", "Weed control status", "Crop Health", "Good/Poor", None, 1, 1),
		]),
		(4, "Vegetative", 25, 45, [
			("CROP_VIGOUR", "Crop vigour", "Crop Health", "Good/Poor", None, 1, 1),
			("THINNING_COMPLETE", "Thinning completed", "Field Work", "Yes/No", None, 1, 1),
			("OFFTYPES_ROUGED", "Off-types rouged", "Seed Quality", "Yes/No", None, 1, 1),
			("PEST_DISEASE_STATUS", "Pest and disease status", "Crop Health", "Good/Poor", None, 1, 1),
			("TOPDRESS_APPLIED", "First top dressing applied", "Inputs", "Yes/No", None, 1, 1),
			("WEED_CONTROL", "Weed control status", "Field Work", "Good/Poor", None, 1, 1),
		]),
		(5, "Pre-flowering", 46, 60, [
			("CROP_UNIFORMITY", "Crop uniformity", "Seed Quality", "Good/Poor", None, 1, 1),
			("ISOLATION_QUALITY", "Isolation distance quality", "Seed Quality", "Good/Poor", None, 1, 1),
			("OFFTYPES_STATUS", "Off-type removal status", "Seed Quality", "Good/Poor", None, 1, 1),
			("SECOND_TOPDRESS", "Second top dressing applied", "Inputs", "Yes/No", None, 1, 1),
			("DETASSEL_READINESS", "Detasselling readiness", "Detasselling", "Good/Poor", None, 1, 1),
			("LABOUR_READY", "Detasselling labour mobilised", "Detasselling", "Yes/No", None, 1, 1),
		]),
		(6, "Flowering", 61, 75, [
			("FLOWERING_PERCENT", "Field flowering percentage", "Flowering", "Percent", "Percent", 1, 0),
			("DETASSEL_STATUS", "Detasselling status", "Detasselling", "Good/Poor", None, 1, 1),
			("FEMALE_POLLEN_SHEDDING", "Female plants shedding pollen", "Seed Quality", "Good/Poor", None, 1, 1),
			("OFFTYPES_STATUS", "Off-type removal status", "Seed Quality", "Good/Poor", None, 1, 1),
			("DISEASE_STATUS", "Disease status", "Crop Health", "Good/Poor", None, 1, 1),
		]),
		(7, "Pre-harvest", 120, 135, [
			("MATURITY_PERCENT", "Crop maturity percentage", "Harvest Readiness", "Percent", "Percent", 1, 0),
			("MALE_LINE_REMOVED", "Male line removed", "Seed Quality", "Yes/No", None, 1, 1),
			("FIELD_PURITY", "Field purity status", "Seed Quality", "Good/Poor", None, 1, 1),
			("EAR_DISEASE_STATUS", "Ear rot, smut and termite status", "Crop Health", "Good/Poor", None, 1, 1),
			("ESTIMATED_YIELD", "Estimated harvest yield", "Harvest Readiness", "Number", "Kg", 1, 0),
		]),
		(8, "Harvest", 150, 180, [
			("HARVEST_DATE", "Harvest date", "Harvest", "Date", None, 1, 0),
			("HARVESTED_AREA", "Area harvested", "Harvest", "Number", "Acre", 1, 0),
			("GROSS_YIELD", "Gross seed yield", "Harvest", "Number", "Kg", 1, 0),
			("REJECTED_QUANTITY", "Rejected quantity", "Quality", "Number", "Kg", 1, 1),
			("MOISTURE_PERCENT", "Seed moisture percentage", "Quality", "Percent", "Percent", 1, 1),
			("SORTING_STATUS", "Sorting and bagging status", "Harvest", "Good/Poor", None, 1, 1),
		]),
		(9, "Delivery", 180, 190, [
			("DELIVERY_DATE", "Delivery date", "Delivery", "Date", None, 1, 0),
			("DELIVERED_QUANTITY", "Delivered quantity", "Delivery", "Number", "Kg", 1, 0),
			("ACCEPTED_QUANTITY", "Accepted quantity", "Delivery", "Number", "Kg", 1, 0),
			("REJECTED_QUANTITY", "Rejected quantity", "Delivery", "Number", "Kg", 1, 1),
			("DELIVERY_MOISTURE", "Delivery moisture percentage", "Quality", "Percent", "Percent", 1, 1),
			("DELIVERY_REFERENCE", "Delivery note or Purchase Receipt", "Delivery", "Data", None, 1, 0),
		]),
	]
	for number, stage_name, start, end, parameters in reports:
		name = f"Report {number} - {stage_name}"
		existing = frappe.db.get_value("Agronomy Report Template", {"report_number": number})
		doc = (
			frappe.get_doc("Agronomy Report Template", existing)
			if existing
			else frappe.new_doc("Agronomy Report Template")
		)
		doc.update(
			{
				"report_name": name,
				"report_number": number,
				"stage_name": stage_name,
				"window_start_day": start,
				"window_end_day": end,
				"active": 1,
				"template_version": cint(doc.template_version) or 1,
				"overall_pass_threshold_percent": 100,
				"critical_failure_override": 1,
				"instructions": (
					"Capture the mandatory raw observations and current GPS position on site."
				),
			}
		)
		doc.set("parameters", [])
		for code, label, section, data_type, unit, mandatory, corrective in parameters:
			rule, minimum_value, maximum_value, expected_value = automated_rules.get(
				code, (None, None, None, None)
			)
			doc.append(
				"parameters",
				{
					"parameter_code": code,
					"parameter_label": label,
					"section_name": section,
					"data_type": data_type,
					"options": "Basic\nCertified" if code == "SEED_CATEGORY" else None,
					"unit": unit,
					"mandatory": mandatory,
					"evaluation_mode": "Rule Based" if rule else "Informational",
					"comparison_rule": rule,
					"minimum_value": minimum_value,
					"maximum_value": maximum_value,
					"expected_value": expected_value,
					"severity": "Critical" if code in critical_parameters else "Standard",
					"weight": 1,
					"allow_not_applicable": 0,
					"responsible_party": "Outgrower Supervisor",
					"corrective_action_on_fail": corrective if rule else 0,
					"failure_action": failure_actions.get(code)
					or f"Correct the failed standard for {label.lower()} and record completion evidence.",
					"corrective_action_due_days": 1 if code in critical_parameters else 3,
				},
			)
		doc.save(ignore_permissions=True)
	print("  ✓ Agronomy Report Templates seeded")
	frappe.db.commit()


def seed_agronomy_activity_templates():
	"""Create supervisor/farmer agronomy activity schedule from planting date."""
	print("\nCreating Agronomy Activity Templates...")
	legacy_template = frappe.db.get_value(
		"Agronomy Activity Template",
		{"activity_name": "Harvesting, sorting and delivery"},
	)
	if legacy_template:
		frappe.db.set_value(
			"Agronomy Activity Template",
			legacy_template,
			"active",
			0,
			update_modified=False,
		)
		for activity in set(
			frappe.get_all(
				"Stage Activity",
				filters={
					"activity_template": legacy_template,
					"status": "Scheduled",
				},
				pluck="name",
			)
			+ frappe.get_all(
				"Stage Activity",
				filters={
					"title": "Harvesting, sorting and delivery",
					"status": "Scheduled",
				},
				pluck="name",
			)
		):
			frappe.delete_doc("Stage Activity", activity, ignore_permissions=True)
	recipe_name = (
		"Maize Production (Standard)"
		if frappe.db.exists("Crop Recipe", "Maize Production (Standard)")
		else None
	)
	activities = [
		(-30, -1, "Recruit and contract outgrower", "Field Verification & Contracting", "Supervisor / Farmer", 0),
		(0, 0, "Planting", "Planting", "Supervisor / Farmer", 0),
		(2, 3, "Spraying", "Planting", "Supervisor / Farmer", 0),
		(10, 10, "Germination check", "Crop Emergence / Germination", "Supervisor / Farmer", 0),
		(15, 15, "Scouting for pests", "Crop Emergence / Germination", "Supervisor / Farmer", 0),
		(21, 21, "Selective herbicide application", "Vegetative", "Supervisor / Farmer", 0),
		(26, 26, "Check herbicide performance", "Vegetative", "Supervisor / Farmer", 0),
		(27, 30, "Thinning and removal of offtypes", "Vegetative", "Supervisor / Farmer", 0),
		(30, 30, "Urea 40% N 6% S application", "Vegetative", "Supervisor / Farmer", 0),
		(31, 35, "Scouting for pests and rouging", "Vegetative", "Supervisor / Farmer", 0),
		(36, 40, "Spot manual weeding", "Vegetative", "Supervisor / Farmer", 0),
		(45, 45, "Second top dress with Urea 46% N", "Pre-flowering", "Supervisor / Farmer / QA", 1),
		(50, 50, "Prepare field for detassling", "Pre-flowering", "Supervisor / Farmer", 0),
		(53, 54, "Mobilise detassling labour", "Pre-flowering", "Farmer", 0),
		(55, 60, "Detassling starts and labour training", "Pre-flowering", "Supervisor / Farmer", 0),
		(60, 70, "Check field for emerging tassels", "Flowering", "Supervisor / Farmer / QA", 1),
		(75, 85, "Scout for ear rot, smut and termites", "Flowering", "Supervisor / Farmer", 0),
		(90, 90, "Male line removal", "Pre-harvest", "Farmer", 0),
		(120, 135, "Pre-harvest inspection readiness", "Pre-harvest", "Supervisor / Farmer / QA", 1),
		(140, 180, "Harvesting and sorting", "Harvest", "Supervisor / Farmer", 0),
		(180, 190, "Deliver accepted seed harvest", "Delivery", "Supervisor / Farmer", 0),
	]
	for start, end, name, stage_name, responsible, inspection_related in activities:
		existing = frappe.db.get_value("Agronomy Activity Template", {"activity_name": name})
		doc = (
			frappe.get_doc("Agronomy Activity Template", existing)
			if existing
			else frappe.new_doc("Agronomy Activity Template")
		)
		doc.update({
			"activity_name": name,
			"crop_recipe": recipe_name,
			"stage_name": stage_name,
			"day_offset_from_planting": start,
			"day_offset_end": end,
			"responsible_party": responsible,
			"priority": "High" if inspection_related else "Medium",
			"mandatory": 1,
			"evidence_required": int(stage_name in ("Planting", "Harvest", "Delivery")),
			"inspection_related": inspection_related,
			"active": 1,
		})
		doc.save(ignore_permissions=True)
		print(f"  ✓ Created Activity: {name}")
	frappe.db.commit()


def seed_sample_fieldops_data():
	"""Create a compact demo farm/crop cycle/inspection for QA workflow testing."""
	print("\nCreating Sample FieldOps Test Data...")

	outgrower = _ensure_doc(
		"Outgrower",
		"SAMPLE-OG-001",
		{
			"outgrower_id": "SAMPLE-OG-001",
			"full_name": "Sample QA Farmer",
			"phone": "+256700000001",
			"registration_date": "2026-03-01",
			"region": "Central",
			"status": "Active",
			"outgrower_type": "Individual",
			"bank_account": "SAMPLE-ACC-001",
		},
	)

	plot = _ensure_doc(
		"Farm Plot",
		"SAMPLE-PLOT-001",
		{
			"plot_id": "SAMPLE-PLOT-001",
			"outgrower": outgrower.name,
			"plot_name": "Sample QA Seed Field",
			"plot_type": "Owned",
			"status": "Active",
			"area_acres": 2.5,
			"polygon": [
				{"latitude": 0.347500, "longitude": 32.582500, "order_index": 1},
				{"latitude": 0.347500, "longitude": 32.583400, "order_index": 2},
				{"latitude": 0.348400, "longitude": 32.583400, "order_index": 3},
				{"latitude": 0.348400, "longitude": 32.582500, "order_index": 4},
			],
		},
	)

	supplier = ensure_outgrower_supplier(outgrower.name)
	contract_name = frappe.db.get_value(
		"Outgrower Production Contract",
		{"farm_plot": plot.name, "docstatus": 1},
		"name",
	)
	if not contract_name:
		contract = frappe.get_doc(
			{
				"doctype": "Outgrower Production Contract",
				"outgrower": outgrower.name,
				"supplier": supplier,
				"farm_plot": plot.name,
				"season": "2026 B",
				"crop": "Maize",
				"variety": "Longe 10H",
				"production_category": "Certified",
				"crop_recipe": "Maize Production (Standard)",
				"pricing_policy": "2026B Maize Certified Seed Pricing",
				"agreement_date": "2026-07-20",
				"contract_start_date": "2026-07-20",
				"contract_end_date": "2027-01-31",
				"planting_start_date": "2026-08-01",
				"planting_end_date": "2026-08-31",
				"expected_harvest_date": "2026-12-15",
				"contracted_area_acres": 2.5,
				"parent_seed_item": FIELDOPS_ITEMS["Maize Seed (Hybrid)"]["item_code"],
				"planned_parent_seed_qty": 50,
				"parent_seed_uom": "Kg",
				"harvest_item": FIELDOPS_ITEMS["Maize Seed Harvest"]["item_code"],
				"expected_yield_qty": 5000,
				"pricing_method": "Fixed Rate",
				"contract_rate": FIELDOPS_ITEMS["Maize Seed Harvest"]["rate"],
				"max_exposure_percent": 70,
				"default_recovery_policy": "Fully Recoverable",
				"input_recovery_terms": "Recover approved inputs and cash advances from accepted harvest value.",
				"minimum_farmer_compliance_percent": 80,
				"minimum_supervisor_compliance_percent": 80,
				"required_isolation_quality": "Good",
				"target_take_spacing_m": 5,
				"quality_standard_terms": "<p>Apply approved stage inspection standards and corrective actions.</p>",
				"farmer_obligations": "<p>Maintain crop identity, isolation and field records.</p>",
				"supervisor_obligations": "<p>Complete agronomy supervision and stage records.</p>",
				"termination_terms": "<p>Material non-compliance may suspend or terminate production.</p>",
				"is_signed": 1,
				"signed_on": "2026-07-20 09:00:00",
				"company_signatory": "Administrator",
			}
		).insert(ignore_permissions=True)
		contract.submit()
		contract_name = contract.name
		print(f"  ✓ Created Outgrower Production Contract: {contract.name}")

	cycle = _ensure_doc(
		"Crop Cycle",
		"SAMPLE-CC-001",
		{
			"crop_cycle_id": "SAMPLE-CC-001",
			"production_contract": contract_name,
			"plot": plot.name,
			"crop": "Maize",
			"variety": "Longe 10H",
			"season": "2026 B",
			"planting_date": "2026-08-05",
			"production_category": "Certified",
			"start_date": "2026-08-05",
			"expected_harvest_date": "2026-12-15",
			"recipe": "Maize Production (Standard)",
			"harvest_item": FIELDOPS_ITEMS["Maize Seed Harvest"]["item_code"],
			"harvest_uom": "Kg",
			"expected_yield_qty": 5000,
			"contract_rate": FIELDOPS_ITEMS["Maize Seed Harvest"]["rate"],
			"max_exposure_percent": 70,
		},
	)
	if cycle.supplier != supplier:
		cycle.supplier = supplier
		cycle.save(ignore_permissions=True)

	if not frappe.db.exists(
		"Crop Production Lot",
		{"crop_cycle": cycle.name, "lot_number": "SAMPLE-LOT-001"},
	):
		frappe.get_doc(
			{
				"doctype": "Crop Production Lot",
				"lot_number": "SAMPLE-LOT-001",
				"crop_cycle": cycle.name,
				"planting_start_date": "2026-08-05",
				"planting_end_date": "2026-08-09",
				"area_acres": 2.5,
				"parent_seed_item": FIELDOPS_ITEMS["Maize Seed (Hybrid)"]["item_code"],
				"parent_seed_qty": 50,
				"parent_seed_uom": "Kg",
			}
		).insert(ignore_permissions=True)
		print("  + Created Crop Production Lot: SAMPLE-LOT-001")

	try:
		from naseco_fieldopsbackend.inspection_scheduler import generate_crop_cycle_schedules

		generate_crop_cycle_schedules(cycle)
	except Exception as e:
		print(f"  ! Could not generate sample schedules: {str(e)}")

	seed_sample_agronomy_report(cycle, plot, outgrower)
	seed_sample_inspection(cycle, plot, outgrower)
	seed_sample_finance_requests(cycle)
	frappe.db.commit()


def seed_sample_season_production_plan():
	"""Create an editable current-season baseline for user acceptance testing."""
	print("\nCreating Sample Season Production Plan...")
	if frappe.db.exists(
		"Season Production Plan",
		{"season": "2026 B", "company": frappe.defaults.get_global_default("company")},
	):
		print("  → Season Production Plan already exists for 2026 B")
		return

	company = frappe.defaults.get_global_default("company")
	if not company:
		print("  ! Default Company is not configured")
		return
	plan = frappe.get_doc(
		{
			"doctype": "Season Production Plan",
			"plan_title": "2026 B Sample Production Plan",
			"season": "2026 B",
			"company": company,
			"outgrower_manager": "Administrator",
			"quality_manager": "Administrator",
			"finance_approver": "Administrator",
			"stores_responsible": "Administrator",
			"maximum_exposure_percent": 70,
			"production_targets": [
				{
					"region": "Central",
					"crop": "Maize",
					"variety": "Longe 10H",
					"production_category": "Certified",
					"crop_recipe": "Maize Production (Standard)",
					"contract_template": "2026B Maize Certified Seed Growers Agreement",
					"pricing_policy": "2026B Maize Certified Seed Pricing",
					"target_outgrowers": 20,
					"target_plots": 20,
					"target_acres": 100,
					"planned_yield_kg_per_acre": 1000,
					"planning_rate": 1850,
					"parent_seed_item": FIELDOPS_ITEMS["Maize Seed (Hybrid)"]["item_code"],
					"parent_seed_rate_per_acre": 20,
					"planting_window_from": "2026-08-01",
					"planting_window_to": "2026-08-31",
					"expected_harvest_date": "2026-12-15",
					"planned_supervisors": 2,
					"planned_inspectors": 2,
				}
			],
		}
	)
	plan.insert(ignore_permissions=True)
	print(f"  ✓ Created Sample Season Production Plan: {plan.name}")


def seed_sample_agronomy_report(cycle, plot, outgrower):
	cycle = frappe.get_doc("Crop Cycle", cycle) if isinstance(cycle, str) else cycle
	plot = frappe.get_doc("Farm Plot", plot) if isinstance(plot, str) else plot
	report_name = frappe.db.get_value(
		"Agronomy Report",
		{
			"crop_cycle": cycle.name,
			"report_template": "Report 2 - Planting",
			"docstatus": ["<", 2],
		},
	)
	if not report_name:
		return
	report = frappe.get_doc("Agronomy Report", report_name)
	if report.docstatus == 1:
		print(f"  → Sample Agronomy Report already submitted: {report.name}")
		return

	values = {
		"PLANTING_DATE": ("date_value", str(cycle.planting_date)),
		"PLANTED_AREA": ("numeric_value", plot.area_acres),
		"SEED_QUANTITY": ("numeric_value", 20),
		"MALE_FEMALE_RATIO": ("text_value", "1:4"),
		"PLANTING_METHOD": ("text_value", "Hand planting"),
		"BASAL_FERTILIZER": ("text_value", "Yes"),
	}
	for row in report.results:
		fieldname, value = values.get(row.parameter_code, ("text_value", "Observed"))
		row.set(fieldname, value)
		row.remarks = "Sample supervisor observation"
	report.update(
		{
			"report_date": cycle.planting_date,
			"latitude": 0.3477,
			"longitude": 32.5827,
			"gps_accuracy_meters": 2.3,
			"location_captured_at": f"{cycle.planting_date} 08:30:00",
			"field_notes": (
				"Planting completed within the contracted window using the approved "
				"seed and basal fertilizer plan."
			),
		}
	)
	report.save(ignore_permissions=True)
	report.submit()
	print(f"  ✓ Submitted Sample Agronomy Report: {report.name}")


def seed_sample_finance_requests(cycle):
	if not frappe.db.exists(
		"Crop Cycle Advance Request",
		{"crop_cycle": cycle.name, "purpose": "Planting labour and field preparation"},
	):
		frappe.get_doc(
			{
				"doctype": "Crop Cycle Advance Request",
				"crop_cycle": cycle.name,
				"request_date": "2026-03-08",
				"requested_amount": 1000000,
				"approved_amount": 750000,
				"purpose": "Planting labour and field preparation",
			}
		).insert(ignore_permissions=True)
		print("  ✓ Created Sample Crop Cycle Advance Request")

	if frappe.db.exists(
		"Stage Input Request",
		{"crop_cycle": cycle.name, "request_id": "SAMPLE-INPUT-001"},
	):
		return
	planting_stage = frappe.db.get_value(
		"Crop Cycle Stage",
		{"crop_cycle": cycle.name, "stage_name": "Planting"},
	)
	seed_item = FIELDOPS_ITEMS["Maize Seed (Hybrid)"]
	frappe.get_doc(
		{
			"doctype": "Stage Input Request",
			"request_id": "SAMPLE-INPUT-001",
			"crop_cycle": cycle.name,
			"stage": planting_stage,
			"request_date": "2026-03-08",
			"required_by": "2026-03-14",
			"notes": "Certified seed for planting",
			"items": [
				{
					"item_code": seed_item["item_code"],
					"requested_qty": 20,
					"approved_qty": 20,
					"uom": seed_item["uom"],
					"recovery_policy": "Fully Recoverable",
					"recoverable_percent": 100,
					"recovery_rate_basis": "Contract Rate",
					"contract_recovery_rate": seed_item["rate"],
				}
			],
		}
	).insert(ignore_permissions=True)
	print("  ✓ Created Sample Stage Input Request")


def seed_sample_inspection(cycle, plot, outgrower):
	takes = [
		{"take_number": 1, "total_plants_counted": 1000, "latitude": 0.34765000, "longitude": 32.58265000, "gps_accuracy_meters": 2.1, "location_sample_count": 5, "location_capture_duration_seconds": 8.2, "location_source": "Sample GNSS", "captured_at": "2026-04-29 09:05:00", "captured_by": frappe.session.user},
		{"take_number": 2, "total_plants_counted": 1000, "latitude": 0.34765000, "longitude": 32.58269500, "gps_accuracy_meters": 2.3, "location_sample_count": 5, "location_capture_duration_seconds": 9.1, "location_source": "Sample GNSS", "captured_at": "2026-04-29 09:20:00", "captured_by": frappe.session.user},
		{"take_number": 3, "total_plants_counted": 1000, "latitude": 0.34769500, "longitude": 32.58269500, "gps_accuracy_meters": 2.0, "location_sample_count": 6, "location_capture_duration_seconds": 10.4, "location_source": "Sample GNSS", "captured_at": "2026-04-29 09:40:00", "captured_by": frappe.session.user},
		{"take_number": 4, "total_plants_counted": 1000, "latitude": 0.34769500, "longitude": 32.58265000, "gps_accuracy_meters": 2.4, "location_sample_count": 5, "location_capture_duration_seconds": 8.8, "location_source": "Sample GNSS", "captured_at": "2026-04-29 10:00:00", "captured_by": frappe.session.user},
		{"take_number": 5, "total_plants_counted": 1000, "latitude": 0.34774000, "longitude": 32.58265000, "gps_accuracy_meters": 2.2, "location_sample_count": 5, "location_capture_duration_seconds": 9.0, "location_source": "Sample GNSS", "captured_at": "2026-04-29 10:15:00", "captured_by": frappe.session.user},
	]
	values_by_take = [
		(0, 0, 0, 2, 0, 0),
		(0, 0, 0, 1, 0, 0),
		(0, 0, 0, 1, 0, 0),
		(0, 0, 0, 1, 0, 0),
		(0, 0, 0, 1, 0, 0),
	]
	parameters = [
		("Offtypes in females", "Both", "Nos"),
		("Offtypes in males", "Both", "Nos"),
		("Volunteers", "Farmer", "Nos"),
		("Late maturers", "Both", "Nos"),
		("Diseased plants", "Farmer", "Nos"),
		("Noxious weeds", "Farmer", "Nos"),
	]
	take_results = []
	for take_number, values in enumerate(values_by_take, start=1):
		for (parameter, responsibility, unit), value in zip(parameters, values):
			take_results.append({
				"take_number": take_number,
				"parameter": parameter,
				"responsibility": responsibility,
				"observed_count": value,
				"measured_value": value,
				"unit": unit,
			})

	inspection_data = {
		"doctype": "Inspection",
		"inspection_id": "SAMPLE-INSP-001",
		"inspection_template": "Pre-flowering",
		"inspection_type": "Pre-flowering",
		"crop_cycle": cycle.name,
		"plot": plot.name,
		"outgrower": outgrower.name,
		"crop": "Maize",
		"season": "2026 B",
		"production_category": "Certified",
		"sampling_protocol_version": "Cumulative Counts V2",
		"scheduled_date": add_days(cycle.planting_date, 45),
		"started_at": "2026-04-29 09:00:00",
		"completed_at": "2026-04-29 10:15:00",
		"assigned_to": frappe.session.user,
		"status": "Awaiting QA Review",
		"recommendation": "Sample inspection: isolation is good; corrective follow-up required for late maturers.",
		"takes": takes,
		"take_results": take_results,
		"inspection_observations": [
			{
				"parameter": "Isolation distance",
				"responsibility": "Outgrower Supervisor",
				"measured_value": 220,
				"unit": "Meter",
				"captured_by": frappe.session.user,
				"captured_at": "2026-04-29 09:05:00",
			},
			{
				"parameter": "Time isolation",
				"responsibility": "Outgrower Supervisor",
				"measured_value": 5,
				"unit": "Week",
				"captured_by": frappe.session.user,
				"captured_at": "2026-04-29 09:05:00",
			},
		],
	}

	existing_name = frappe.db.get_value("Inspection", {"inspection_id": "SAMPLE-INSP-001"}, "name")
	if existing_name:
		inspection = frappe.get_doc("Inspection", existing_name)
		if inspection.status in (
			"Completed",
			"Awaiting QA Review",
			"Verified",
			"Reinspection Required",
		):
			inspection.flags.allow_completed_update = True
		inspection.update({key: value for key, value in inspection_data.items() if key not in ("doctype", "takes", "take_results", "inspection_observations")})
		inspection.set("takes", takes)
		inspection.set("take_results", take_results)
		inspection.set("inspection_observations", inspection_data["inspection_observations"])
		inspection.save(ignore_permissions=True)
		print("  ✓ Updated Sample Inspection: SAMPLE-INSP-001")
	else:
		inspection = frappe.get_doc(inspection_data)
		inspection.insert(ignore_permissions=True)
		print("  ✓ Created Sample Inspection: SAMPLE-INSP-001")


def _ensure_doc(doctype, name, data):
	if frappe.db.exists(doctype, name):
		print(f"  → {doctype} already exists: {name}")
		doc = frappe.get_doc(doctype, name)
		doc.update(data)
		doc.save(ignore_permissions=True)
		return doc
	doc = frappe.get_doc({"doctype": doctype, **data})
	doc.insert(ignore_permissions=True)
	print(f"  ✓ Created {doctype}: {name}")
	return doc


if __name__ == "__main__":
	execute()
