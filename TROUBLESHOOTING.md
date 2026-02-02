# NASECO FieldOps - Troubleshooting Guide

## Issue: Seed Data Script Fails

### Problem
When running the seed data script:
```bash
bench --site naseco.local execute naseco_fieldopsbackend.fixtures.seed_data.execute
```

You get errors like:
- `LinkValidationError: Could not find Crop: Maize`
- `NameError: name 'naseco_fieldopsbackend' is not defined`

### Root Cause
1. Reference DocTypes were missing `autoname` field configurations
2. The seed script needed better error handling

### Solution

**Step 1: Migrate the Database First**

This is critical - you must migrate before running the seed script:

```bash
bench --site naseco.local migrate
bench --site naseco.local clear-cache
```

**Step 2: Run the Seed Script Using Console**

Use this method instead:

```bash
bench --site naseco.local console
```

Then in the console:
```python
from naseco_fieldopsbackend.fixtures.seed_data import execute
execute()
exit()
```

**Alternative: Direct Python Method**

Or run it directly:
```bash
cd ~/frappe-bench
bench --site naseco.local console << 'EOF'
from naseco_fieldopsbackend.fixtures.seed_data import execute
execute()
EOF
```

**Step 3: Verify the Data**

Check that data was created:
```bash
bench --site naseco.local console
```

```python
import frappe
# Check Crops
print("Crops:", frappe.get_all("Crop", pluck="name"))

# Check Varieties
print("Varieties:", frappe.get_all("Crop Variety", pluck="name"))

# Check Regions
print("Regions:", frappe.get_all("Region", pluck="name"))

exit()
```

---

## What Was Fixed

### 1. Added `autoname` Fields to DocTypes

The following DocTypes were updated with autoname configurations:

- **Crop**: `autoname: "field:crop_name"`
- **Crop Variety**: `autoname: "field:variety_name"`
- **Season**: `autoname: "field:season_name"`
- **Region**: `autoname: "field:region_name"`
- **Unit**: `autoname: "field:unit_name"`
- **Visit Type**: `autoname: "field:type_name"`
- **Crop Recipe**: `autoname: "field:recipe_name"`

This ensures that document names match the field values (e.g., Crop "Maize" has name "Maize").

### 2. Enhanced Error Handling in Seed Script

The seed script now:
- ✅ Commits after each record creation
- ✅ Catches and logs errors without stopping
- ✅ Verifies dependencies exist before creating records
- ✅ Provides clear error messages

---

## Common Issues & Solutions

### Issue: "DocType not found"

**Symptom**: Error says a DocType doesn't exist

**Solution**:
```bash
# Migrate the database
bench --site naseco.local migrate

# Clear cache
bench --site naseco.local clear-cache

# Restart bench
bench restart
```

### Issue: "Permission denied"

**Symptom**: Cannot create records due to permissions

**Solution**:
- The seed script uses `ignore_permissions=True`
- Make sure you're running as Administrator
- If still failing, check role permissions in User DocType

### Issue: Duplicate records

**Symptom**: Script says records already exist

**Solution**:
- This is expected behavior - the script checks before creating
- If you want to recreate, delete existing records first:

```python
# In console
import frappe

# Delete all Crops
frappe.db.sql("DELETE FROM `tabCrop`")
frappe.db.commit()

# Then re-run seed script
from naseco_fieldopsbackend.fixtures.seed_data import execute
execute()
```

### Issue: Link validation errors

**Symptom**: `Could not find Crop: Maize` or similar

**Solution**:
1. Ensure migration ran successfully
2. Check that parent records exist:
   ```python
   frappe.db.exists("Crop", "Maize")  # Should return True
   ```
3. If parent doesn't exist, create it manually or re-run that section

---

## Manual Data Creation (If Seed Script Fails)

If the seed script continues to fail, you can create data manually:

### Create Crops
```python
crops = ["Maize", "Rice", "Soybean", "Beans", "Groundnuts", "Sunflower"]
for crop_name in crops:
    if not frappe.db.exists("Crop", crop_name):
        doc = frappe.get_doc({
            "doctype": "Crop",
            "crop_name": crop_name
        })
        doc.insert()
        frappe.db.commit()
```

### Create Regions
```python
regions = ["Northern", "Central", "Southern", "Eastern", "Western"]
for region_name in regions:
    if not frappe.db.exists("Region", region_name):
        doc = frappe.get_doc({
            "doctype": "Region",
            "region_name": region_name
        })
        doc.insert()
        frappe.db.commit()
```

### Create Units
```python
units = ["kg", "L", "bags", "acres", "grams", "ml", "pieces", "cm", "meters"]
for unit_name in units:
    if not frappe.db.exists("Unit", unit_name):
        doc = frappe.get_doc({
            "doctype": "Unit",
            "unit_name": unit_name
        })
        doc.insert()
        frappe.db.commit()
```

---

## Checking Your Installation

Run this verification script:

```bash
bench --site naseco.local console
```

```python
import frappe

def check_installation():
    print("\n" + "="*60)
    print("NASECO FieldOps Installation Check")
    print("="*60 + "\n")

    # Check DocTypes
    doctypes = [
        "Outgrower", "Farm Plot", "Crop Cycle", "Field Visit",
        "Crop", "Crop Variety", "Season", "Region", "Unit",
        "Visit Type", "Inspection Attribute", "Sync Log"
    ]

    print("Checking DocTypes...")
    for dt in doctypes:
        exists = frappe.db.exists("DocType", dt)
        status = "✓" if exists else "✗"
        print(f"  {status} {dt}")

    # Check Reference Data
    print("\nChecking Reference Data...")
    print(f"  Crops: {len(frappe.get_all('Crop'))}")
    print(f"  Varieties: {len(frappe.get_all('Crop Variety'))}")
    print(f"  Regions: {len(frappe.get_all('Region'))}")
    print(f"  Units: {len(frappe.get_all('Unit'))}")
    print(f"  Visit Types: {len(frappe.get_all('Visit Type'))}")
    print(f"  Seasons: {len(frappe.get_all('Season'))}")
    print(f"  Inspection Attributes: {len(frappe.get_all('Inspection Attribute'))}")

    print("\n" + "="*60 + "\n")

check_installation()
exit()
```

Expected output:
```
✓ All DocTypes should exist
✓ Should see counts for all reference data
```

---

## Still Having Issues?

1. **Check Frappe logs**:
   ```bash
   bench --site naseco.local logs
   ```

2. **Check database**:
   ```bash
   bench --site naseco.local mariadb
   ```
   ```sql
   SHOW TABLES LIKE '%Crop%';
   SELECT * FROM `tabCrop`;
   ```

3. **Reinstall the app**:
   ```bash
   bench --site naseco.local uninstall-app naseco_fieldopsbackend
   bench --site naseco.local install-app naseco_fieldopsbackend
   bench --site naseco.local migrate
   ```

4. **Contact Support**:
   - Check error logs in `~/frappe-bench/sites/naseco.local/logs/`
   - Share error messages for specific help

---

**Last Updated**: February 2026
