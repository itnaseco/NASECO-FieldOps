# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from datetime import datetime


@frappe.whitelist()
def bulk_sync(data):
	"""
	Bulk create/update records from mobile app

	Args:
		data: JSON string containing list of records to sync
			  Format: [{"doctype": "DocType", "operation": "CREATE/UPDATE/DELETE", "doc": {...}}]

	Returns:
		JSON response with success/failure status for each record
	"""
	try:
		records = json.loads(data) if isinstance(data, str) else data
		results = []

		for record in records:
			try:
				doctype = record.get("doctype")
				operation = record.get("operation")
				doc_data = record.get("doc")

				result = {
					"doctype": doctype,
					"operation": operation,
					"status": "success"
				}

				if operation == "CREATE":
					doc = frappe.get_doc(doc_data)
					doc.insert(ignore_permissions=False)
					result["name"] = doc.name

				elif operation == "UPDATE":
					doc_name = doc_data.get("name")
					if frappe.db.exists(doctype, doc_name):
						doc = frappe.get_doc(doctype, doc_name)
						doc.update(doc_data)
						doc.save(ignore_permissions=False)
						result["name"] = doc.name
					else:
						# Document doesn't exist, create it
						doc = frappe.get_doc(doc_data)
						doc.insert(ignore_permissions=False)
						result["name"] = doc.name

				elif operation == "DELETE":
					doc_name = doc_data.get("name")
					if frappe.db.exists(doctype, doc_name):
						frappe.delete_doc(doctype, doc_name, ignore_permissions=False)
						result["name"] = doc_name
					else:
						result["status"] = "not_found"
						result["message"] = f"Document {doctype} {doc_name} not found"

				# Log successful sync
				log_sync(frappe.session.user, doctype, doc_data.get("name"), operation, "Success")

			except Exception as e:
				result["status"] = "error"
				result["message"] = str(e)

				# Log failed sync
				log_sync(
					frappe.session.user,
					record.get("doctype"),
					record.get("doc", {}).get("name"),
					record.get("operation"),
					"Failed",
					str(e)
				)

			results.append(result)

		frappe.db.commit()
		return {
			"success": True,
			"results": results
		}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(f"Bulk sync error: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def get_modified_records(last_sync_timestamp, doctypes=None):
	"""
	Get all records modified since last sync timestamp

	Args:
		last_sync_timestamp: ISO format timestamp of last sync
		doctypes: Optional JSON list of doctypes to fetch. If None, fetches all synced doctypes.

	Returns:
		JSON response with modified records grouped by doctype
	"""
	try:
		# Parse last sync timestamp
		if isinstance(last_sync_timestamp, str):
			last_sync = datetime.fromisoformat(last_sync_timestamp.replace('Z', '+00:00'))
		else:
			last_sync = last_sync_timestamp

		# Default synced doctypes
		default_doctypes = [
			"Outgrower", "Farm Plot", "Crop Cycle", "Crop Cycle Stage",
			"Field Visit", "Finding", "Stage Input Request", "Stage Input Dispatch",
			"Attendance", "Leave Application", "Employee Advance", "Expense Claim"
		]

		# Parse doctypes filter
		if doctypes:
			target_doctypes = json.loads(doctypes) if isinstance(doctypes, str) else doctypes
		else:
			target_doctypes = default_doctypes

		modified_records = {}

		for doctype in target_doctypes:
			try:
				# Get modified records
				records = frappe.get_all(
					doctype,
					filters=[
						["modified", ">", last_sync]
					],
					fields=["*"],
					order_by="modified asc"
				)

				# Get full documents with child tables
				full_records = []
				for record in records:
					try:
						doc = frappe.get_doc(doctype, record.name)
						full_records.append(doc.as_dict())
					except Exception as e:
						frappe.log_error(f"Error fetching {doctype} {record.name}: {str(e)}")

				if full_records:
					modified_records[doctype] = full_records

			except Exception as e:
				frappe.log_error(f"Error fetching modified {doctype}: {str(e)}")

		return {
			"success": True,
			"modified_records": modified_records,
			"sync_timestamp": datetime.now().isoformat()
		}

	except Exception as e:
		frappe.log_error(f"Get modified records error: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def get_reference_data():
	"""
	Get all reference/metadata entities for mobile app

	Returns:
		JSON response with all reference data
	"""
	try:
		reference_data = {}

		# List of reference doctypes
		reference_doctypes = {
			"Crop": ["*"],
			"Crop Variety": ["*"],
			"Season": ["*"],
			"Crop Recipe": ["*"],
			"Visit Type": ["*"],
			"Region": ["*"],
			"Unit": ["*"],
			"Inspection Attribute": ["*"]
		}

		for doctype, fields in reference_doctypes.items():
			try:
				records = frappe.get_all(doctype, fields=fields)
				reference_data[doctype] = records
			except Exception as e:
				frappe.log_error(f"Error fetching reference {doctype}: {str(e)}")

		return {
			"success": True,
			"reference_data": reference_data,
			"timestamp": datetime.now().isoformat()
		}

	except Exception as e:
		frappe.log_error(f"Get reference data error: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}


def log_sync(user, doctype, doc_name, operation, status, error_message=None):
	"""Helper function to log sync operations"""
	try:
		sync_log = frappe.get_doc({
			"doctype": "Sync Log",
			"user": user,
			"doctype_name": doctype,
			"doc_name": doc_name,
			"operation": operation,
			"status": status,
			"error_message": error_message,
			"sync_timestamp": datetime.now()
		})
		sync_log.insert(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(f"Error logging sync: {str(e)}")


@frappe.whitelist()
def check_conflicts(doctype, doc_name, mobile_modified):
	"""
	Check if a record has conflicts between mobile and server

	Args:
		doctype: DocType name
		doc_name: Document name
		mobile_modified: Mobile's last modified timestamp

	Returns:
		Conflict status and server data if conflict exists
	"""
	try:
		if not frappe.db.exists(doctype, doc_name):
			return {
				"has_conflict": False,
				"reason": "not_found"
			}

		server_doc = frappe.get_doc(doctype, doc_name)
		server_modified = server_doc.modified

		# Parse mobile modified timestamp
		mobile_modified_dt = datetime.fromisoformat(mobile_modified.replace('Z', '+00:00'))

		# Check if server version is newer
		if server_modified > mobile_modified_dt:
			return {
				"has_conflict": True,
				"server_data": server_doc.as_dict(),
				"server_modified": server_modified.isoformat()
			}

		return {
			"has_conflict": False
		}

	except Exception as e:
		frappe.log_error(f"Check conflicts error: {str(e)}")
		return {
			"has_conflict": False,
			"error": str(e)
		}
