import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def create_doctypes():
    print(" Creating DocTypes for Naseco FieldOpsBackend...")

    # 1. Child Tables
    child_tables = [
        {
            "doctype": "DocType",
            "name": "Recipe Stage",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "istable": 1,
            "fields": [
                {"fieldname": "stage_name", "label": "Stage Name", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
                {"fieldname": "order_index", "label": "Order", "fieldtype": "Int", "reqd": 1, "in_list_view": 1},
                {"fieldname": "duration_days", "label": "Duration (Days)", "fieldtype": "Int", "in_list_view": 1},
                {"fieldname": "inputs", "label": "Inputs JSON", "fieldtype": "Code", "options": "JSON"}
            ]
        },
        {
            "doctype": "DocType",
            "name": "Visit Finding",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "istable": 1,
            "fields": [
                {"fieldname": "attribute", "label": "Attribute", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
                {"fieldname": "value", "label": "Value", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
                {"fieldname": "unit", "label": "Unit", "fieldtype": "Data", "in_list_view": 1},
                {"fieldname": "remarks", "label": "Remarks", "fieldtype": "Data"}
            ]
        }
    ]

    process_doctypes(child_tables)

    # 2. Reference & Core DocTypes
    doctypes = [
        # Reference Data
        {
            "doctype": "DocType",
            "name": "Region",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "fields": [{"fieldname": "region_name", "label": "Region Name", "fieldtype": "Data", "reqd": 1}]
        },
        {
            "doctype": "DocType",
            "name": "Crop",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "fields": [{"fieldname": "crop_name", "label": "Crop Name", "fieldtype": "Data", "reqd": 1}]
        },
        {
            "doctype": "DocType",
            "name": "Season",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "fields": [
                {"fieldname": "season_name", "label": "Season Name", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "start_date", "label": "Start Date", "fieldtype": "Date"},
                {"fieldname": "end_date", "label": "End Date", "fieldtype": "Date"}
            ]
        },
        {
            "doctype": "DocType",
            "name": "Crop Variety",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "fields": [
                {"fieldname": "variety_name", "label": "Variety Name", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "crop", "label": "Crop", "fieldtype": "Link", "options": "Crop", "reqd": 1},
                {"fieldname": "maturity_days", "label": "Maturity Days", "fieldtype": "Int"}
            ]
        },
        {
            "doctype": "DocType",
            "name": "Visit Type",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "fields": [{"fieldname": "type_name", "label": "Type Name", "fieldtype": "Data", "reqd": 1}]
        },
        {
            "doctype": "DocType",
            "name": "Unit",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "fields": [{"fieldname": "unit_name", "label": "Unit Name", "fieldtype": "Data", "reqd": 1}]
        },
        
        # Core Entities
        {
            "doctype": "DocType",
            "name": "Outgrower",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "autoname": "field:outgrower_id",
            "fields": [
                {"fieldname": "outgrower_id", "label": "Outgrower ID", "fieldtype": "Data", "reqd": 1, "unique": 1},
                {"fieldname": "full_name", "label": "Full Name", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "phone", "label": "Phone", "fieldtype": "Data"},
                {"fieldname": "region", "label": "Region", "fieldtype": "Link", "options": "Region"},
                {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Active\nInactive\nBlacklisted", "default": "Active"}
            ]
        },
        {
            "doctype": "DocType",
            "name": "Farm Plot",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "autoname": "field:plot_id",
            "fields": [
                {"fieldname": "plot_id", "label": "Plot ID", "fieldtype": "Data", "reqd": 1, "unique": 1},
                {"fieldname": "outgrower", "label": "Outgrower", "fieldtype": "Link", "options": "Outgrower", "reqd": 1},
                {"fieldname": "area_acres", "label": "Area (Acres)", "fieldtype": "Float"},
                {"fieldname": "geojson", "label": "GeoJSON", "fieldtype": "Code", "options": "JSON"},
                {"fieldname": "map_image", "label": "Map Image", "fieldtype": "Attach Image"},
                {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Active\nIdle", "default": "Active"}
            ]
        },
        {
            "doctype": "DocType",
            "name": "Crop Recipe",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "fields": [
                {"fieldname": "recipe_name", "label": "Recipe Name", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "crop", "label": "Crop", "fieldtype": "Link", "options": "Crop", "reqd": 1},
                {"fieldname": "stages", "label": "Stages", "fieldtype": "Table", "options": "Recipe Stage"}
            ]
        },
        {
            "doctype": "DocType",
            "name": "Crop Cycle",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "autoname": "field:crop_cycle_id",
            "fields": [
                {"fieldname": "crop_cycle_id", "label": "Cycle ID", "fieldtype": "Data", "reqd": 1, "unique": 1},
                {"fieldname": "plot", "label": "Plot", "fieldtype": "Link", "options": "Farm Plot", "reqd": 1},
                {"fieldname": "crop", "label": "Crop", "fieldtype": "Link", "options": "Crop", "reqd": 1},
                {"fieldname": "variety", "label": "Variety", "fieldtype": "Link", "options": "Crop Variety"},
                {"fieldname": "season", "label": "Season", "fieldtype": "Link", "options": "Season"},
                {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "PLANNED\nACTIVE\nCOMPLETED"}
            ]
        },
        {
            "doctype": "DocType",
            "name": "Field Visit",
            "module": "Naseco FieldOpsBackend",
            "custom": 0,
            "autoname": "field:visit_id",
            "fields": [
                {"fieldname": "visit_id", "label": "Visit ID", "fieldtype": "Data", "reqd": 1, "unique": 1},
                {"fieldname": "plot", "label": "Plot", "fieldtype": "Link", "options": "Farm Plot"},
                {"fieldname": "crop_cycle", "label": "Crop Cycle", "fieldtype": "Link", "options": "Crop Cycle"},
                {"fieldname": "visit_type", "label": "Visit Type", "fieldtype": "Link", "options": "Visit Type"},
                {"fieldname": "timestamp", "label": "Done At", "fieldtype": "Datetime"},
                {"fieldname": "findings", "label": "Findings", "fieldtype": "Table", "options": "Visit Finding"},
                {"fieldname": "notes", "label": "Notes", "fieldtype": "Text"}
            ]
        }
    ]

    process_doctypes(doctypes)
    frappe.db.commit()

def process_doctypes(doctypes):
    for dt_config in doctypes:
        print(f" Processing {dt_config['name']}...")
        if frappe.db.exists("DocType", dt_config["name"]):
            doc = frappe.get_doc("DocType", dt_config["name"])
            # Update to standard if it was custom
            doc.custom = 0
            doc.module = "Naseco FieldOpsBackend"
            doc.istable = dt_config.get("istable", 0)
            
            # Reset Permissions (Ensure we don't duplicate on re-run)
            doc.permissions = []
            doc.append("permissions", {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1})
            
            doc.save()
            print(f" [UPDATED] {dt_config['name']} saved as Standard DocType")
        else:
            try:
                doc = frappe.get_doc(dt_config)
                doc.append("permissions", {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1})
                doc.insert()
                print(f" [CREATED] {dt_config['name']} created as Standard DocType")
            except Exception as e:
                print(f" [ERROR] Failed to create {dt_config['name']}: {str(e)}")

def create_cust_fields():
    print(" Creating Custom Fields for HRMS...")
    custom_fields = {
        "Attendance": [
            {"fieldname": "mobile_id", "label": "Mobile ID", "fieldtype": "Data", "unique": 1, "read_only": 1, "insert_after": "naming_series"},
            {"fieldname": "attendance_id", "label": "Attendance ID", "fieldtype": "Data", "unique": 1, "insert_after": "mobile_id"},
            {"fieldname": "check_in_time", "label": "Check In Time", "fieldtype": "Datetime", "insert_after": "attendance_id"},
            {"fieldname": "check_out_time", "label": "Check Out Time", "fieldtype": "Datetime", "insert_after": "check_in_time"},
            {"fieldname": "late_entry", "label": "Late Entry", "fieldtype": "Check", "insert_after": "check_out_time"},
            {"fieldname": "early_exit", "label": "Early Exit", "fieldtype": "Check", "insert_after": "late_entry"},
            {"fieldname": "total_distance_km", "label": "Total Distance (Km)", "fieldtype": "Float", "insert_after": "early_exit"},
            {"fieldname": "check_in_lat", "label": "Check In Lat", "fieldtype": "Float", "precision": 6, "insert_after": "total_distance_km"},
            {"fieldname": "check_in_lng", "label": "Check In Lng", "fieldtype": "Float", "precision": 6, "insert_after": "check_in_lat"},
            {"fieldname": "check_out_lat", "label": "Check Out Lat", "fieldtype": "Float", "precision": 6, "insert_after": "check_in_lng"},
            {"fieldname": "check_out_lng", "label": "Check Out Lng", "fieldtype": "Float", "precision": 6, "insert_after": "check_out_lat"}
        ],
        "Employee Checkin": [
            {"fieldname": "checkin_id", "label": "Checkin ID", "fieldtype": "Data", "unique": 1, "insert_after": "name"},
            {"fieldname": "user_id", "label": "User", "fieldtype": "Link", "options": "User", "insert_after": "checkin_id"},
            {"fieldname": "user_email", "label": "User Email", "fieldtype": "Data", "options": "Email", "insert_after": "user_id"},
            {"fieldname": "latitude", "label": "Latitude", "fieldtype": "Float", "precision": 6, "insert_after": "user_email"},
            {"fieldname": "longitude", "label": "Longitude", "fieldtype": "Float", "precision": 6, "insert_after": "latitude"},
            {"fieldname": "device_id", "label": "Device ID", "fieldtype": "Data", "insert_after": "longitude"},
            {"fieldname": "synced", "label": "Synced", "fieldtype": "Check", "default": 0, "insert_after": "device_id"}
        ],
        "Leave Application": [
             {"fieldname": "mobile_id", "label": "Mobile ID", "fieldtype": "Data", "unique": 1, "read_only": 1, "insert_after": "naming_series"},
             {"fieldname": "application_id", "label": "Application ID", "fieldtype": "Data", "unique": 1, "insert_after": "mobile_id"},
             {"fieldname": "approver_email", "label": "Approver Email", "fieldtype": "Data", "options": "Email", "insert_after": "application_id"},
             {"fieldname": "approver_name", "label": "Approver Name", "fieldtype": "Data", "insert_after": "approver_email"},
             {"fieldname": "attachments_json", "label": "Attachments (JSON)", "fieldtype": "Long Text", "insert_after": "approver_name"}
        ],
        "Employee Advance": [
             {"fieldname": "mobile_id", "label": "Mobile ID", "fieldtype": "Data", "unique": 1, "read_only": 1, "insert_after": "naming_series"},
             {"fieldname": "advance_id", "label": "Advance ID", "fieldtype": "Data", "unique": 1, "insert_after": "mobile_id"},
             {"fieldname": "repay_from_salary", "label": "Repay From Salary", "fieldtype": "Check", "default": 0, "insert_after": "advance_id"},
             {"fieldname": "attachments_json", "label": "Attachments (JSON)", "fieldtype": "Long Text", "insert_after": "repay_from_salary"}
        ],
        "Expense Claim": [
             {"fieldname": "mobile_id", "label": "Mobile ID", "fieldtype": "Data", "unique": 1, "read_only": 1, "insert_after": "naming_series"},
             {"fieldname": "expense_id", "label": "Expense ID", "fieldtype": "Data", "unique": 1, "insert_after": "mobile_id"},
             {"fieldname": "category", "label": "Category", "fieldtype": "Data", "insert_after": "expense_id"},
             {"fieldname": "date_submitted", "label": "Date Submitted", "fieldtype": "Date", "insert_after": "category"}
         ]
    }

    try:
        create_custom_fields(custom_fields)
        print(" [OK] Custom Fields Created")
    except Exception as e:
        print(f" [ERROR] Failed to create custom fields: {str(e)}")

    frappe.db.commit()

if __name__ == "__main__":
    create_doctypes()
    create_cust_fields()
