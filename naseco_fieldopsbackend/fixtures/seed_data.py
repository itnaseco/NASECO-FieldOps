# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute():
	"""Seed reference data for NASECO FieldOps"""
	print("\n" + "="*60)
	print("Seeding Reference Data for NASECO FieldOps")
	print("="*60 + "\n")

	# Seed in correct order (respecting dependencies)
	try:
		seed_regions()
		seed_units()
		seed_crops()
		seed_varieties()
		seed_seasons()
		seed_visit_types()
		seed_inspection_attributes()

		print("\n" + "="*60)
		print("Seeding Completed Successfully!")
		print("="*60 + "\n")
	except Exception as e:
		print(f"\n✗ Seeding failed: {str(e)}")
		frappe.db.rollback()
		raise


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


def seed_units():
	"""Create units of measurement"""
	print("\nCreating Units...")
	units = [
		{"unit_name": "kg"},
		{"unit_name": "L"},
		{"unit_name": "bags"},
		{"unit_name": "acres"},
		{"unit_name": "grams"},
		{"unit_name": "ml"},
		{"unit_name": "pieces"},
		{"unit_name": "cm"},
		{"unit_name": "meters"}
	]

	for unit_data in units:
		try:
			if not frappe.db.exists("Unit", unit_data["unit_name"]):
				doc = frappe.get_doc({
					"doctype": "Unit",
					**unit_data
				})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				print(f"  ✓ Created Unit: {unit_data['unit_name']}")
			else:
				print(f"  → Unit already exists: {unit_data['unit_name']}")
		except Exception as e:
			print(f"  ✗ Error creating Unit {unit_data['unit_name']}: {str(e)}")
			frappe.db.rollback()


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
		{"season_name": "Season A 2026", "start_date": "2026-03-01", "end_date": "2026-08-31"}
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
				print(f"  → Season already exists: {season_name}")
		except Exception as e:
			print(f"  ✗ Error creating Season {season_name}: {str(e)}")
			frappe.db.rollback()


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
		{"attribute_name": "Plant Height", "attribute_type": "Numeric", "unit": "cm"},
		{"attribute_name": "Plant Population", "attribute_type": "Numeric", "unit": "pieces"},
		{"attribute_name": "Leaf Color", "attribute_type": "Text"},
		{"attribute_name": "Pest Presence", "attribute_type": "Boolean"},
		{"attribute_name": "Disease Symptoms", "attribute_type": "Text"},
		{"attribute_name": "Soil Moisture", "attribute_type": "Text"},
		{"attribute_name": "Weed Pressure", "attribute_type": "Text"},
		{"attribute_name": "Flowering Stage", "attribute_type": "Boolean"},
		{"attribute_name": "Expected Yield", "attribute_type": "Numeric", "unit": "kg"},
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


if __name__ == "__main__":
	execute()
