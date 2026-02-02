# NASECO FieldOps Backend - Implementation Guide

## Overview

This guide provides step-by-step instructions for setting up and using the NASECO FieldOps Frappe custom app. The app manages outgrower farmers, plot mapping with GPS polygons, crop lifecycle tracking, field visits, findings, input management, and sync functionality for mobile apps.

## Table of Contents

1. [Installation](#installation)
2. [Initial Setup](#initial-setup)
3. [DocTypes Created](#doctypes-created)
4. [Business Logic Implemented](#business-logic-implemented)
5. [API Endpoints](#api-endpoints)
6. [Usage Examples](#usage-examples)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites

- Frappe Framework installed
- ERPNext (optional, for HR modules)
- Python 3.10+
- MariaDB 10.6+

### Installation Steps

```bash
# Navigate to your bench directory
cd ~/frappe-bench

# Install the app (if not already installed)
bench get-app naseco_fieldopsbackend

# Install on your site
bench --site your-site-name install-app naseco_fieldopsbackend

# Migrate database
bench --site your-site-name migrate

# Clear cache
bench --site your-site-name clear-cache
```

## Initial Setup

### 1. Run Seed Data Script

The seed data script creates all reference data needed for the system.

```bash
# Option 1: Using bench console
bench --site your-site-name console

# In the console
from naseco_fieldopsbackend.fixtures.seed_data import execute
execute()
exit()

# Option 2: Direct execution
bench --site your-site-name execute naseco_fieldopsbackend.fixtures.seed_data.execute
```

This will create:
- **Regions**: Northern, Central, Southern, Eastern, Western
- **Units**: kg, L, bags, acres, grams, ml, pieces, cm, meters
- **Crops**: Maize, Rice, Soybean, Beans, Groundnuts, Sunflower
- **Crop Varieties**: Multiple varieties for each crop
- **Seasons**: Season A/B for 2024-2026
- **Visit Types**: Routine, Emergency, Planting, Harvest, etc.
- **Inspection Attributes**: Plant Height, Leaf Color, Pest Presence, etc.

### 2. Create Users and Roles

Set up the following roles for your field operations team:

- **NASECO Admin**: Full access to all DocTypes
- **NASECO Manager**: Read/Write operational data
- **Field Officer**: Read/Write own records
- **Expense Approver**: Approve expense claims
- **Leave Approver**: Approve leave applications
- **Finance Manager**: Manage salary advances

## DocTypes Created

### Core Synced DocTypes (Bidirectional Sync with Mobile)

#### 1. **Outgrower**
Represents contract farmers.

**Key Fields:**
- `outgrower_id`: Unique identifier
- `full_name`: Farmer's full name
- `phone`: Contact number
- `registration_date`: When they joined
- `years_since_registration`: Auto-calculated
- `farmer_status`: Auto-calculated (Beginner/Intermediate/Experienced/Expert)
- `region`: Link to Region
- `assigned_to`: Assigned field officer

**Business Logic:**
- Auto-calculates years since registration
- Auto-updates farmer status based on years:
  - Beginner: < 1 year
  - Intermediate: 1-2 years
  - Experienced: 2-5 years
  - Expert: 5+ years

#### 2. **Farm Plot**
Agricultural land with GPS polygon boundaries.

**Key Fields:**
- `plot_id`: Unique identifier
- `outgrower`: Link to Outgrower
- `plot_name`: Descriptive name
- `plot_type`: Owned/Leased/Shared
- `polygon`: Child table of Plot Vertex (GPS coordinates)
- `area_acres`: Auto-calculated from polygon
- `perimeter_meters`: Auto-calculated from polygon
- `centroid_lat/lng`: Auto-calculated center point
- `geojson`: Auto-generated GeoJSON representation

**Business Logic:**
- Calculates area using spherical polygon formula
- Calculates perimeter using Haversine distance
- Calculates centroid using unit vector averaging
- Generates GeoJSON for mapping
- **Requires minimum 3 vertices**

**UI Features:**
- "View on Map" button displays interactive map with Leaflet.js
- Dashboard indicators show area and perimeter
- Sortable polygon vertex table

#### 3. **Crop Cycle**
Complete crop lifecycle from planting to harvest.

**Key Fields:**
- `crop_cycle_id`: Unique identifier
- `plot`: Link to Farm Plot
- `crop`: Link to Crop
- `variety`: Link to Crop Variety
- `season`: Link to Season
- `recipe`: Link to Crop Recipe
- `start_date`: Planting date
- `expected_harvest_date`: Projected harvest
- `actual_harvest_date`: Actual harvest
- `current_stage`: Link to Crop Cycle Stage
- `status`: Auto-calculated (PLANNED/ACTIVE/COMPLETED)

**Business Logic:**
- Auto-updates status based on dates:
  - PLANNED: start_date in future
  - ACTIVE: started but not harvested
  - COMPLETED: actual_harvest_date set

#### 4. **Crop Cycle Stage**
Individual stages in a crop cycle.

**Key Fields:**
- `crop_cycle`: Link to Crop Cycle
- `stage_name`: Name of stage (e.g., "Germination", "Flowering")
- `order_index`: Sequence number
- `start_date/end_date`: Stage duration
- `status`: Pending/In Progress/Completed/Skipped
- `completion_percentage`: Progress indicator
- `inputs`: Child table of required inputs

#### 5. **Field Visit**
Field visit records with GPS validation.

**Key Fields:**
- `visit_id`: Unique identifier
- `plot`: Link to Farm Plot
- `crop_cycle`: Link to Crop Cycle
- `stage`: Link to Crop Cycle Stage
- `visit_type`: Link to Visit Type
- `gps_lat/lng`: Visit GPS coordinates
- `distance_from_plot`: Auto-calculated distance from plot centroid
- `timestamp`: Visit date and time
- `visited_by`: Link to User
- `photos`: Child table of Visit Photo
- `findings`: Child table of Visit Finding
- `notes`: Text notes

**Business Logic:**
- Calculates distance from visit GPS to plot centroid
- Warns if distance > 5km from plot
- Validates GPS proximity

#### 6. **Finding**
Individual observations during visits (separate from child table).

**Key Fields:**
- `finding_id`: Unique identifier
- `visit`: Link to Field Visit
- `crop_cycle`: Link to Crop Cycle
- `stage`: Link to Crop Cycle Stage
- `attribute`: Link to Inspection Attribute
- `value`: Observation value
- `unit`: Link to Unit
- `remarks`: Additional notes
- `photos`: Child table of Finding Photo

#### 7. **Stage Input Request**
Request for crop inputs (seeds, fertilizer, etc.).

**Key Fields:**
- `request_id`: Unique identifier
- `crop_cycle`: Link to Crop Cycle
- `stage`: Link to Crop Cycle Stage
- `input_name`: Name of input needed
- `quantity_needed`: Amount required
- `unit`: Link to Unit
- `quantity_dispatched`: Auto-calculated from dispatches
- `quantity_remaining`: Auto-calculated
- `status`: Pending/Approved/Partially Fulfilled/Fulfilled/Rejected

**Business Logic:**
- Calculates total dispatched quantity from all related dispatches
- Auto-updates status based on fulfillment:
  - Pending: No dispatches yet
  - Approved: Approved but not dispatched
  - Partially Fulfilled: Some dispatched
  - Fulfilled: Fully dispatched

**UI Features:**
- Fulfillment progress indicator with color coding
- "Create Dispatch" button
- "View Dispatches" button
- Dashboard shows remaining quantity

#### 8. **Stage Input Dispatch**
Dispatch/delivery of requested inputs.

**Key Fields:**
- `dispatch_id`: Unique identifier
- `input_request`: Link to Stage Input Request
- `crop_cycle`: Auto-populated from request
- `stage`: Auto-populated from request
- `input_name`: Auto-populated from request
- `quantity_dispatched`: Amount dispatched
- `unit`: Link to Unit
- `dispatch_date`: Date of dispatch
- `dispatched_by`: Link to User
- `received_by`: Link to User

**Business Logic:**
- Auto-populates fields from parent request
- Updates parent request fulfillment status on save/delete

### Reference/Metadata DocTypes (Pull-only for Mobile)

9. **Crop**: Master list of crops
10. **Crop Variety**: Varieties for each crop with maturity days
11. **Season**: Agricultural seasons with date ranges
12. **Crop Recipe**: Template for crop management stages
13. **Visit Type**: Types of field visits
14. **Region**: Geographic regions
15. **Unit**: Units of measurement
16. **Inspection Attribute**: Attributes to observe during visits

### System DocTypes

17. **Sync Log**: Tracks all sync operations from mobile
18. **Sync Conflict**: Records conflicts for manual resolution
19. **Plot Vertex**: Child table for GPS polygon vertices
20. **Visit Photo**: Child table for visit photos
21. **Finding Photo**: Child table for finding photos
22. **Recipe Input Item**: Child table for recipe inputs

## Business Logic Implemented

### 1. Geospatial Calculations (Farm Plot)

**Location**: `farm_plot.py`

```python
# Automatically calculates:
- Area in acres using spherical polygon formula
- Perimeter in meters using Haversine distance
- Centroid (center point) using unit vector averaging
- GeoJSON representation for mapping
```

**Formula Used:**
- **Area**: Spherical excess formula for accurate calculation on Earth's surface
- **Perimeter**: Sum of Haversine distances between consecutive vertices
- **Centroid**: Unit vector averaging in Cartesian coordinates

### 2. Status Auto-Calculation

**Outgrower Status** (`outgrower.py`):
- Calculates years since registration
- Updates farmer status automatically

**Crop Cycle Status** (`crop_cycle.py`):
- PLANNED: start_date > today
- ACTIVE: start_date <= today and no harvest date
- COMPLETED: actual_harvest_date is set

### 3. GPS Distance Validation (Field Visit)

**Location**: `field_visit.py`

- Calculates distance from visit GPS to plot centroid
- Warns if distance > 5km
- Stores calculated distance in `distance_from_plot` field

### 4. Input Request/Dispatch Logic

**Stage Input Request** (`stage_input_request.py`):
- Sums all related dispatches
- Updates `quantity_dispatched` automatically
- Updates status based on fulfillment

**Stage Input Dispatch** (`stage_input_dispatch.py`):
- Auto-populates fields from parent request
- Triggers parent request update on save/delete

## API Endpoints

All API endpoints are defined in `api.py`.

### 1. Bulk Sync

**Endpoint**: `/api/method/naseco_fieldopsbackend.api.bulk_sync`
**Method**: POST
**Auth**: Required (session-based)

**Purpose**: Bulk create/update/delete records from mobile app

**Request Body**:
```json
{
  "data": [
    {
      "doctype": "Farm Plot",
      "operation": "CREATE",
      "doc": {
        "plot_id": "PLOT-001",
        "outgrower": "OUT-001",
        "plot_name": "North Field",
        "polygon": [
          {"latitude": 0.3476, "longitude": 32.5825, "order_index": 1},
          {"latitude": 0.3477, "longitude": 32.5826, "order_index": 2},
          {"latitude": 0.3478, "longitude": 32.5824, "order_index": 3}
        ]
      }
    }
  ]
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "doctype": "Farm Plot",
      "operation": "CREATE",
      "status": "success",
      "name": "PLOT-001"
    }
  ]
}
```

### 2. Get Modified Records

**Endpoint**: `/api/method/naseco_fieldopsbackend.api.get_modified_records`
**Method**: GET
**Auth**: Required

**Purpose**: Get all records modified since last sync

**Parameters**:
- `last_sync_timestamp`: ISO format timestamp (e.g., "2026-02-01T10:00:00Z")
- `doctypes`: Optional JSON array of doctypes to fetch

**Response**:
```json
{
  "success": true,
  "modified_records": {
    "Farm Plot": [
      {
        "name": "PLOT-001",
        "plot_id": "PLOT-001",
        "modified": "2026-02-02T14:30:00",
        ...
      }
    ],
    "Field Visit": [...]
  },
  "sync_timestamp": "2026-02-02T15:00:00"
}
```

### 3. Get Reference Data

**Endpoint**: `/api/method/naseco_fieldopsbackend.api.get_reference_data`
**Method**: GET
**Auth**: Required

**Purpose**: Get all reference/metadata for mobile app initialization

**Response**:
```json
{
  "success": true,
  "reference_data": {
    "Crop": [...],
    "Crop Variety": [...],
    "Season": [...],
    "Visit Type": [...],
    "Region": [...],
    "Unit": [...],
    "Inspection Attribute": [...]
  },
  "timestamp": "2026-02-02T15:00:00"
}
```

### 4. Check Conflicts

**Endpoint**: `/api/method/naseco_fieldopsbackend.api.check_conflicts`
**Method**: GET
**Auth**: Required

**Purpose**: Check if a record has conflicts between mobile and server

**Parameters**:
- `doctype`: DocType name
- `doc_name`: Document name
- `mobile_modified`: Mobile's last modified timestamp

**Response**:
```json
{
  "has_conflict": true,
  "server_data": {...},
  "server_modified": "2026-02-02T14:45:00"
}
```

## Usage Examples

### Example 1: Create an Outgrower

```python
import frappe

# Create outgrower
outgrower = frappe.get_doc({
    "doctype": "Outgrower",
    "outgrower_id": "OG-001",
    "full_name": "John Mukasa",
    "phone": "+256700123456",
    "email": "john@example.com",
    "registration_date": "2023-01-15",
    "region": "Central",
    "assigned_to": "user@example.com"
})
outgrower.insert()

# Years and status are auto-calculated
print(f"Years: {outgrower.years_since_registration}")
print(f"Status: {outgrower.farmer_status}")
```

### Example 2: Create a Plot with GPS Polygon

```python
# Create plot with vertices
plot = frappe.get_doc({
    "doctype": "Farm Plot",
    "plot_id": "PLOT-001",
    "outgrower": "OG-001",
    "plot_name": "North Field",
    "plot_type": "Owned",
    "polygon": [
        {"latitude": 0.3476, "longitude": 32.5825, "order_index": 1},
        {"latitude": 0.3477, "longitude": 32.5826, "order_index": 2},
        {"latitude": 0.3478, "longitude": 32.5827, "order_index": 3},
        {"latitude": 0.3479, "longitude": 32.5824, "order_index": 4}
    ]
})
plot.insert()

# Area, perimeter, and centroid are auto-calculated
print(f"Area: {plot.area_acres} acres")
print(f"Perimeter: {plot.perimeter_meters} meters")
print(f"Centroid: {plot.centroid_lat}, {plot.centroid_lng}")
```

### Example 3: Create a Crop Cycle

```python
# Create crop cycle
cycle = frappe.get_doc({
    "doctype": "Crop Cycle",
    "crop_cycle_id": "CC-001",
    "plot": "PLOT-001",
    "crop": "Maize",
    "variety": "Longe 10H",
    "season": "Season A 2026",
    "start_date": "2026-03-15",
    "expected_harvest_date": "2026-07-15"
})
cycle.insert()

# Status is auto-calculated
print(f"Status: {cycle.status}")  # Will be PLANNED or ACTIVE based on dates
```

### Example 4: Create a Field Visit

```python
# Create field visit
visit = frappe.get_doc({
    "doctype": "Field Visit",
    "visit_id": "VIS-001",
    "plot": "PLOT-001",
    "crop_cycle": "CC-001",
    "visit_type": "Routine Inspection",
    "gps_lat": 0.3477,
    "gps_lng": 32.5825,
    "timestamp": "2026-04-01 10:30:00",
    "visited_by": "user@example.com",
    "findings": [
        {
            "attribute": "Plant Height",
            "value": "45",
            "unit": "cm",
            "remarks": "Good growth"
        }
    ],
    "notes": "All plants looking healthy"
})
visit.insert()

# Distance is auto-calculated
print(f"Distance from plot: {visit.distance_from_plot} km")
```

### Example 5: Input Request and Dispatch

```python
# Create input request
request = frappe.get_doc({
    "doctype": "Stage Input Request",
    "crop_cycle": "CC-001",
    "stage": "Stage-001",
    "input_name": "NPK Fertilizer",
    "quantity_needed": 50,
    "unit": "kg",
    "requested_by": "user@example.com"
})
request.insert()

# Create dispatch
dispatch = frappe.get_doc({
    "doctype": "Stage Input Dispatch",
    "input_request": request.name,
    "quantity_dispatched": 30,
    "dispatch_date": "2026-04-05",
    "dispatched_by": "warehouse@example.com"
})
dispatch.insert()

# Request status is auto-updated to "Partially Fulfilled"
request.reload()
print(f"Status: {request.status}")
print(f"Dispatched: {request.quantity_dispatched} / {request.quantity_needed}")
```

## Testing

### Manual Testing Steps

1. **Test Outgrower Creation**:
   - Go to Outgrower list
   - Create new outgrower with registration date in past
   - Verify years_since_registration and farmer_status are auto-calculated

2. **Test Plot Geospatial Calculations**:
   - Create new Farm Plot
   - Add 3+ vertices to polygon table
   - Save and verify area, perimeter, centroid are calculated
   - Click "View on Map" to see visualization

3. **Test Crop Cycle Status**:
   - Create crop cycle with future start date → Status should be PLANNED
   - Edit start date to past → Status should change to ACTIVE
   - Add actual harvest date → Status should change to COMPLETED

4. **Test Field Visit GPS Validation**:
   - Create field visit for a plot
   - Enter GPS coordinates far from plot (>5km)
   - Save and verify warning message appears

5. **Test Input Request/Dispatch**:
   - Create input request for 100 kg
   - Verify status is "Pending"
   - Create dispatch for 50 kg
   - Reload request → Status should be "Partially Fulfilled"
   - Create another dispatch for 50 kg
   - Reload request → Status should be "Fulfilled"

### API Testing

```bash
# Test bulk_sync
curl -X POST \
  http://your-site/api/method/naseco_fieldopsbackend.api.bulk_sync \
  -H 'Cookie: sid=your_session_id' \
  -H 'Content-Type: application/json' \
  -d '{"data": [...]}'

# Test get_modified_records
curl -X GET \
  "http://your-site/api/method/naseco_fieldopsbackend.api.get_modified_records?last_sync_timestamp=2026-02-01T00:00:00Z" \
  -H 'Cookie: sid=your_session_id'

# Test get_reference_data
curl -X GET \
  http://your-site/api/method/naseco_fieldopsbackend.api.get_reference_data \
  -H 'Cookie: sid=your_session_id'
```

## Troubleshooting

### Issue: Geospatial calculations not working

**Solution**:
- Verify polygon has at least 3 vertices
- Check that latitude/longitude values are valid
- Ensure order_index is sequential

### Issue: Status not auto-updating

**Solution**:
- Check that date fields are populated
- Verify server scripts are enabled
- Check error log for Python exceptions

### Issue: API endpoints returning authentication errors

**Solution**:
- Ensure user is logged in
- Check API permissions for the user's role
- Verify session cookie is being sent

### Issue: Sync conflicts

**Solution**:
- Check Sync Conflict DocType for unresolved conflicts
- Use `check_conflicts` API before syncing
- Implement conflict resolution strategy in mobile app

### Issue: Client scripts not loading

**Solution**:
- Clear browser cache
- Run `bench clear-cache`
- Check browser console for JavaScript errors

## Next Steps

1. **Set up Workflows**: Create approval workflows for HR operations
2. **Configure Permissions**: Set up role-based permissions
3. **Test Mobile Integration**: Test all API endpoints with mobile app
4. **Train Users**: Conduct training for field officers
5. **Monitor Performance**: Set up logging and monitoring

## Support

For issues or questions:
1. Check Frappe error log: `bench --site your-site logs`
2. Review this guide
3. Contact NASECO technical team

---

**Version**: 1.0
**Last Updated**: February 2026
**Maintainer**: NASECO Technical Team
