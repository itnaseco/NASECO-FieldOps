from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Add the v2 take-session audit fields without altering historical rows."""
	create_custom_fields(
		{
			"Inspection Take": [
				{"fieldname": "start_latitude", "label": "Start Latitude", "fieldtype": "Float", "precision": "8", "insert_after": "take_number"},
				{"fieldname": "start_longitude", "label": "Start Longitude", "fieldtype": "Float", "precision": "8", "insert_after": "start_latitude"},
				{"fieldname": "start_gps_accuracy_meters", "label": "Start GPS Accuracy (m)", "fieldtype": "Float", "insert_after": "start_longitude"},
				{"fieldname": "started_at", "label": "Take Started At", "fieldtype": "Datetime", "insert_after": "start_gps_accuracy_meters"},
				{"fieldname": "end_latitude", "label": "End Latitude", "fieldtype": "Float", "precision": "8", "insert_after": "started_at"},
				{"fieldname": "end_longitude", "label": "End Longitude", "fieldtype": "Float", "precision": "8", "insert_after": "end_latitude"},
				{"fieldname": "end_gps_accuracy_meters", "label": "End GPS Accuracy (m)", "fieldtype": "Float", "insert_after": "end_longitude"},
				{"fieldname": "ended_at", "label": "Take Ended At", "fieldtype": "Datetime", "insert_after": "end_gps_accuracy_meters"},
				{"fieldname": "take_distance_m", "label": "Take Distance (m)", "fieldtype": "Float", "read_only": 1, "insert_after": "ended_at"},
				{"fieldname": "capture_exception_codes", "label": "Capture Exception Codes", "fieldtype": "Small Text", "read_only": 1, "insert_after": "take_distance_m"},
			],
		},
		update=True,
	)
