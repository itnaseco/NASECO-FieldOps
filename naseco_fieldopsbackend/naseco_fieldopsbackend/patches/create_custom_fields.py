import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
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

    create_custom_fields(custom_fields)
    frappe.db.commit()
