# Copyright (c) 2026, NASECO and contributors
# Test script to create a sample plot with GPS polygon

import frappe
from datetime import datetime


def create_test_plot():
	"""Create a test outgrower and plot with GPS polygon"""

	print("\n" + "="*60)
	print("Creating Test Plot with GPS Polygon")
	print("="*60 + "\n")

	# Step 1: Create test outgrower
	print("Step 1: Creating test outgrower...")
	outgrower_id = "OG-TEST-001"

	if not frappe.db.exists("Outgrower", outgrower_id):
		outgrower = frappe.get_doc({
			"doctype": "Outgrower",
			"outgrower_id": outgrower_id,
			"full_name": "John Test Farmer",
			"phone": "+256700123456",
			"email": "test@example.com",
			"registration_date": "2023-01-15",
			"region": "Central"  # Make sure this region exists
		})
		outgrower.insert(ignore_permissions=True)
		frappe.db.commit()
		print(f"  ✓ Created Outgrower: {outgrower_id}")
		print(f"    - Years Since Registration: {outgrower.years_since_registration}")
		print(f"    - Farmer Status: {outgrower.farmer_status}")
	else:
		print(f"  → Outgrower already exists: {outgrower_id}")
		outgrower = frappe.get_doc("Outgrower", outgrower_id)

	# Step 2: Create test plot with GPS vertices
	print("\nStep 2: Creating test plot with GPS polygon...")
	plot_id = "PLOT-TEST-001"

	if frappe.db.exists("Farm Plot", plot_id):
		print(f"  → Plot already exists: {plot_id}")
		print("  → Deleting old plot to create fresh one...")
		frappe.delete_doc("Farm Plot", plot_id, force=1)
		frappe.db.commit()

	# Create plot with vertices
	plot = frappe.get_doc({
		"doctype": "Farm Plot",
		"plot_id": plot_id,
		"outgrower": outgrower_id,
		"plot_name": "North Test Field",
		"plot_type": "Owned",
		"polygon": [
			{
				"latitude": 0.3476,
				"longitude": 32.5825,
				"order_index": 1
			},
			{
				"latitude": 0.3477,
				"longitude": 32.5826,
				"order_index": 2
			},
			{
				"latitude": 0.3478,
				"longitude": 32.5827,
				"order_index": 3
			},
			{
				"latitude": 0.3479,
				"longitude": 32.5824,
				"order_index": 4
			}
		]
	})

	plot.insert(ignore_permissions=True)
	frappe.db.commit()

	print(f"  ✓ Created Plot: {plot_id}")
	print(f"\n" + "-"*60)
	print("GEOSPATIAL CALCULATIONS RESULTS:")
	print("-"*60)
	print(f"  📍 Vertices: {len(plot.polygon)} points")
	print(f"  📐 Area: {plot.area_acres} acres")
	print(f"  📏 Perimeter: {plot.perimeter_meters} meters")
	print(f"  🎯 Centroid: ({plot.centroid_lat}, {plot.centroid_lng})")
	print("-"*60)

	# Display vertices
	print("\nVertices:")
	for vertex in plot.polygon:
		print(f"  {vertex.order_index}. Lat: {vertex.latitude}, Lng: {vertex.longitude}")

	# Display GeoJSON (first 200 chars)
	if plot.geojson:
		print(f"\nGeoJSON Generated: Yes ({len(plot.geojson)} characters)")
		print(f"Preview: {plot.geojson[:200]}...")

	print("\n" + "="*60)
	print("✓ Test Plot Created Successfully!")
	print("="*60)
	print("\nNext Steps:")
	print("1. Open Farm Plot list in Frappe")
	print(f"2. Find plot: {plot_id}")
	print("3. Click 'View on Map' button to see visualization")
	print("4. Verify area, perimeter, and centroid calculations")
	print("\n")

	return plot


def delete_test_data():
	"""Delete test data"""
	print("\nDeleting test data...")

	if frappe.db.exists("Farm Plot", "PLOT-TEST-001"):
		frappe.delete_doc("Farm Plot", "PLOT-TEST-001", force=1)
		print("  ✓ Deleted test plot")

	if frappe.db.exists("Outgrower", "OG-TEST-001"):
		frappe.delete_doc("Outgrower", "OG-TEST-001", force=1)
		print("  ✓ Deleted test outgrower")

	frappe.db.commit()
	print("✓ Test data deleted\n")


if __name__ == "__main__":
	create_test_plot()
