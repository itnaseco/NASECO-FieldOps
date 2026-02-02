# NASECO FieldOps - Quick Start Guide

Get your NASECO FieldOps backend running in **5 minutes**! ⚡

---

## Step 1: Migrate Database (30 seconds)

```bash
cd ~/frappe-bench
bench --site your-site-name migrate
bench --site your-site-name clear-cache
```

---

## Step 2: Seed Reference Data (1 minute)

Run the seed script to populate all reference data:

```bash
bench --site your-site-name execute naseco_fieldopsbackend.fixtures.seed_data.execute
```

This creates:
- ✅ 5 Regions (Northern, Central, Southern, Eastern, Western)
- ✅ 9 Units (kg, L, bags, acres, etc.)
- ✅ 6 Crops (Maize, Rice, Soybean, etc.)
- ✅ 10 Crop Varieties
- ✅ 5 Seasons (2024-2026)
- ✅ 8 Visit Types
- ✅ 10 Inspection Attributes

---

## Step 3: Quick Test (3 minutes)

### Test 1: Create an Outgrower

1. Go to **Outgrower** list
2. Click **New**
3. Fill in:
   - Outgrower ID: `OG-001`
   - Full Name: `John Mukasa`
   - Phone: `+256700123456`
   - Registration Date: `2023-01-15` (past date)
   - Region: `Central`
4. **Save**

✅ **Verify**: `Years Since Registration` and `Farmer Status` are auto-calculated!

### Test 2: Create a Plot with GPS

1. Go to **Farm Plot** list
2. Click **New**
3. Fill in:
   - Plot ID: `PLOT-001`
   - Outgrower: `OG-001`
   - Plot Name: `North Field`
4. Add vertices in **Polygon** table:
   - Vertex 1: Lat `0.3476`, Lng `32.5825`, Order `1`
   - Vertex 2: Lat `0.3477`, Lng `32.5826`, Order `2`
   - Vertex 3: Lat `0.3478`, Lng `32.5827`, Order `3`
   - Vertex 4: Lat `0.3479`, Lng `32.5824`, Order `4`
5. **Save**

✅ **Verify**: Area, Perimeter, and Centroid are auto-calculated!
✅ **Click** "View on Map" button to see the plot visualization!

### Test 3: Test API Endpoint

```bash
# Get reference data
curl -X GET \
  "http://localhost:8000/api/method/naseco_fieldopsbackend.api.get_reference_data" \
  -H "Authorization: token YOUR_API_KEY:YOUR_API_SECRET"
```

✅ **Verify**: Returns JSON with all reference data!

---

## Step 4: Configure for Mobile App

### Set Up API User

1. Create a new User for mobile app
2. Generate API Key and Secret:
   ```bash
   bench --site your-site-name console
   ```
   ```python
   from frappe.utils import generate_hash
   api_key = generate_hash(length=15)
   api_secret = generate_hash(length=15)
   print(f"API Key: {api_key}")
   print(f"API Secret: {api_secret}")
   ```

3. Update user with API credentials in User DocType

### Test Sync Endpoint

```bash
# Test bulk sync
curl -X POST \
  http://localhost:8000/api/method/naseco_fieldopsbackend.api.bulk_sync \
  -H "Authorization: token YOUR_API_KEY:YOUR_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      {
        "doctype": "Outgrower",
        "operation": "CREATE",
        "doc": {
          "outgrower_id": "OG-002",
          "full_name": "Jane Nakato",
          "phone": "+256700987654",
          "registration_date": "2024-01-01",
          "region": "Northern"
        }
      }
    ]
  }'
```

---

## 🎉 You're Done!

Your NASECO FieldOps backend is now **fully operational**!

---

## What's Next?

### For Developers:
- Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for detailed documentation
- Review [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for what was built
- Test all API endpoints with your Flutter mobile app

### For Admins:
- Set up user roles and permissions
- Create additional outgrowers and plots
- Configure workflows for HR operations
- Train field officers on the system

### Key Features to Explore:

1. **🗺️ Plot Map Visualization**
   - Open any Farm Plot with GPS vertices
   - Click "View on Map" button
   - See interactive Leaflet.js map

2. **📊 Input Request Tracking**
   - Create a Stage Input Request
   - Create partial dispatches
   - Watch fulfillment progress update automatically

3. **📍 GPS Distance Validation**
   - Create a Field Visit far from plot
   - See automatic warning if > 5km away

4. **🤖 Auto-Calculations**
   - Outgrower status updates automatically
   - Crop cycle status changes with dates
   - Plot area/perimeter calculated from GPS

---

## Troubleshooting

**Issue**: Geospatial calculations not working
- ✅ Ensure plot has at least 3 vertices
- ✅ Check latitude/longitude are valid numbers
- ✅ Verify order_index is sequential (1, 2, 3...)

**Issue**: API returns authentication error
- ✅ Check API key and secret are correct
- ✅ Ensure user has proper permissions
- ✅ Verify Authorization header format

**Issue**: Client scripts not loading
- ✅ Run `bench --site your-site-name clear-cache`
- ✅ Hard refresh browser (Ctrl+Shift+R)
- ✅ Check browser console for errors

---

## Support

For detailed documentation:
- 📘 [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - Complete reference
- 📊 [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - What was built

For issues:
- Check Frappe error log: `bench --site your-site-name logs`
- Contact NASECO technical team

---

**Happy Coding! 🚀**
