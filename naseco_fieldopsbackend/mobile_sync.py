"""Durable, user-scoped mobile change delivery for the offline Flutter app.

Frappe remains authoritative. Document hooks append an opaque ledger row in
the same transaction as the business change. Socket.IO only wakes connected
clients; clients fetch authoritative, permission-scoped deltas over HTTP.
"""

from __future__ import annotations

from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import add_days, cint, now_datetime

CHANGE_DOCTYPE = "Mobile Sync Change"
REALTIME_EVENT = "fieldops_mobile_changed"
DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500
RETENTION_DAYS = 30
RECIPIENT_CACHE_SECONDS = 300

# Keep this aligned with api.get_sync_data. Child-table rows are transported
# through their parent document and therefore do not need their own events.
MOBILE_SYNC_DOCTYPES = {
	"Attendance",
	"Employee Checkin",
	"Outgrower",
	"Farm Plot",
	"Crop Cycle",
	"Crop Cycle Stage",
	"Field Visit",
	"Field Trip",
	"Inspection",
	"Agronomy Report",
	"Field Corrective Action",
	"Plot Crop Assignment",
	"Stage Activity",
	"Stage Input Request",
	"Stage Input Dispatch",
	"Crop Production Lot",
	"Seed Harvest Quality Assessment",
	"Expense Claim",
	"Leave Application",
	"Employee Advance",
	"Crop",
	"Crop Variety",
	"Season",
	"Crop Recipe",
	"Visit Type",
	"Region",
	"UOM",
	"Inspection Attribute",
	"Inspection Parameter",
	"Inspection Template",
	"Inspection Standard",
	"Inspection Template Parameter",
	"Inspection Template Applicability",
	"Agronomy Activity Template",
	"Agronomy Report Template",
}

# A change to one of these fields can add/remove whole relationship trees from
# a field user's scope. The delta still carries the changed record, while this
# flag instructs the client to reconcile its complete authorized snapshot.
SCOPE_FIELDS = {
	"Outgrower": {"assigned_supervisor"},
	"Farm Plot": {"outgrower"},
	"Crop Cycle": {"plot"},
	"Inspection": {"assigned_to", "outgrower", "plot", "crop_cycle"},
	"Agronomy Report": {"assigned_supervisor", "crop_cycle"},
	"Stage Activity": {"assigned_to", "crop_cycle"},
	"Field Visit": {"plot", "crop_cycle"},
	"Field Trip": {"field_officer"},
	"Field Corrective Action": {"assigned_to", "verification_assigned_to", "crop_cycle"},
	"Stage Input Request": {"crop_cycle"},
	"Stage Input Dispatch": {"crop_cycle"},
	"Crop Production Lot": {"crop_cycle"},
	"Seed Harvest Quality Assessment": {"inspected_by", "crop_cycle", "outgrower"},
	"Plot Crop Assignment": {"crop_cycle", "plot"},
	"Attendance": {"employee"},
	"Employee Checkin": {"employee"},
	"Expense Claim": {"employee"},
	"Leave Application": {"employee"},
	"Employee Advance": {"employee"},
}

# These documents perform server-side updates to other mobile-visible records.
# A full reconciliation is safer than assuming the initiating document is the
# only record affected.
CASCADE_RECONCILE_DOCTYPES = {
	"Crop Cycle",
	"Stage Activity",
	"Inspection Template",
	"Seed Harvest Quality Assessment",
	"Stage Input Dispatch",
	"Stage Input Request",
	"Inspection",
	"Agronomy Report",
}


def _api():
	from naseco_fieldopsbackend import api

	return api


def _external_id(doc):
	fieldname = _api().ID_FIELD_MAP.get(doc.doctype)
	return doc.get(fieldname) if fieldname else None


def _requires_full_sync(doc, *, deleting=False):
	if doc.doctype in CASCADE_RECONCILE_DOCTYPES:
		return True
	fields = SCOPE_FIELDS.get(doc.doctype, set())
	if deleting and fields:
		return True
	return any(doc.has_value_changed(fieldname) for fieldname in fields)


def _eligible_mobile_users():
	"""Return enabled users that can authenticate to the field mobile app."""
	from naseco_fieldopsbackend.roles import (
		OUTGROWER_MANAGER_ROLE,
		OUTGROWER_SUPERVISOR_ROLE,
		QUALITY_INSPECTOR_ROLE,
		QUALITY_MANAGER_ROLE,
	)

	roles = {
		OUTGROWER_MANAGER_ROLE,
		OUTGROWER_SUPERVISOR_ROLE,
		QUALITY_INSPECTOR_ROLE,
		QUALITY_MANAGER_ROLE,
		"System Manager",
	}
	users = set(
		frappe.get_all(
			"Has Role",
			filters={"role": ["in", list(roles)], "parenttype": "User"},
			pluck="parent",
		)
	)
	users.update(
		frappe.get_all(
			"Employee",
			filters={"status": "Active", "user_id": ["is", "set"]},
			pluck="user_id",
		)
	)
	if not users:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", list(users)], "enabled": 1, "user_type": "System User"},
		pluck="name",
	)


def _cached_eligible_mobile_users():
	cache_key = "naseco_fieldopsbackend:mobile_sync:eligible_users"
	cached = frappe.cache.get_value(cache_key)
	if cached is not None:
		return cached
	users = _eligible_mobile_users()
	frappe.cache.set_value(
		cache_key,
		users,
		expires_in_sec=RECIPIENT_CACHE_SECONDS,
	)
	return users


def _publish_change(cursor):
	# Send no document identity or payload. The authenticated HTTP endpoint is
	# the only place that resolves permissions and returns business data.
	for user in _cached_eligible_mobile_users():
		frappe.publish_realtime(
			REALTIME_EVENT,
			{"cursor": cursor},
			user=user,
			after_commit=True,
		)


def _append_change(doc, operation, *, requires_full_sync=False):
	if doc.doctype not in MOBILE_SYNC_DOCTYPES:
		return None
	store = _api().DOCTYPE_TO_STORE.get(doc.doctype, doc.doctype)
	change = frappe.get_doc(
		{
			"doctype": CHANGE_DOCTYPE,
			"document_type": doc.doctype,
			"document_name": doc.name,
			"external_id": _external_id(doc),
			"store_name": store,
			"operation": operation,
			"requires_full_sync": cint(requires_full_sync),
			"source_modified": doc.get("modified"),
		}
	).insert(ignore_permissions=True)
	_publish_change(change.name)
	return change.name


def record_mobile_change(doc, method=None):
	"""Document hook for inserts, saves and Document.db_set() updates."""
	if doc.doctype == CHANGE_DOCTYPE or doc.doctype not in MOBILE_SYNC_DOCTYPES:
		return
	_append_change(
		doc,
		"upsert",
		requires_full_sync=_requires_full_sync(doc),
	)


def record_mobile_deletion(doc, method=None):
	"""Write a tombstone before deletion; rollback removes it if delete fails."""
	if doc.doctype == CHANGE_DOCTYPE or doc.doctype not in MOBILE_SYNC_DOCTYPES:
		return
	_append_change(
		doc,
		"remove",
		requires_full_sync=_requires_full_sync(doc, deleting=True),
	)


def record_direct_mobile_change(doctype, name, *, requires_full_sync=False):
	"""Record a direct frappe.db.set_value update that bypasses doc events."""
	if doctype not in MOBILE_SYNC_DOCTYPES or not name or not frappe.db.exists(doctype, name):
		return None
	doc = frappe.get_doc(doctype, name)
	return _append_change(
		doc,
		"upsert",
		requires_full_sync=requires_full_sync,
	)


def _latest_cursor():
	rows = frappe.get_all(CHANGE_DOCTYPE, fields=["name"], order_by="name desc", limit=1)
	return rows[0].name if rows else "0"


def _cursor_expired(cursor):
	if not cursor or cursor == "0" or frappe.db.exists(CHANGE_DOCTYPE, cursor):
		return False
	rows = frappe.get_all(CHANGE_DOCTYPE, fields=["name"], order_by="name asc", limit=1)
	return bool(rows and cursor < rows[0].name)


def _in_current_scope(doctype, name):
	names = _api()._mobile_scope_names(doctype)
	return names is None or name in names


def _add_deletion(deletions, store, *identifiers):
	target = deletions.setdefault(store, [])
	for identifier in identifiers:
		if identifier and identifier not in target:
			target.append(identifier)


@frappe.whitelist()
def get_mobile_changes(cursor=None, limit=DEFAULT_PAGE_SIZE):
	"""Return authoritative mobile deltas after an opaque ledger cursor."""
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Authentication is required."), frappe.PermissionError)

	limit = max(1, min(cint(limit) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))
	latest = _latest_cursor()
	if not cursor or cursor == "0":
		return {
			"data": {},
			"deletions": {},
			"cursor": latest,
			"has_more": False,
			"requires_full_sync": True,
			"reason": "bootstrap",
		}
	if _cursor_expired(cursor):
		return {
			"data": {},
			"deletions": {},
			"cursor": latest,
			"has_more": False,
			"requires_full_sync": True,
			"reason": "cursor_expired",
		}

	rows = frappe.get_all(
		CHANGE_DOCTYPE,
		filters={"name": [">", cursor]},
		fields=[
			"name",
			"document_type",
			"document_name",
			"external_id",
			"store_name",
			"operation",
			"requires_full_sync",
		],
		order_by="name asc",
		limit=limit + 1,
	)
	has_more = len(rows) > limit
	page = rows[:limit]
	allowed = _api()._mobile_allowed_doctypes("read")
	latest_by_document = OrderedDict()
	for row in page:
		latest_by_document[(row.document_type, row.document_name)] = row

	data = {}
	deletions = {}
	requires_full_sync = any(cint(row.requires_full_sync) for row in page)
	for row in latest_by_document.values():
		if row.document_type not in allowed:
			continue
		if row.operation == "remove" or not frappe.db.exists(row.document_type, row.document_name):
			_add_deletion(deletions, row.store_name, row.document_name, row.external_id)
			continue
		if not _in_current_scope(row.document_type, row.document_name):
			_add_deletion(deletions, row.store_name, row.document_name, row.external_id)
			continue
		doc = frappe.get_doc(row.document_type, row.document_name).as_dict()
		mapped = _api()._map_doc_to_mobile(row.document_type, doc)
		data.setdefault(row.store_name, []).append(mapped)

	return {
		"data": data,
		"deletions": deletions,
		"cursor": page[-1].name if page else cursor,
		"has_more": has_more,
		"requires_full_sync": requires_full_sync,
		"reason": "scope_changed" if requires_full_sync else None,
	}


def prune_mobile_sync_changes():
	"""Keep the ledger bounded; expired cursors force a safe full snapshot."""
	frappe.db.delete(
		CHANGE_DOCTYPE,
		{"creation": ["<", add_days(now_datetime(), -RETENTION_DAYS)]},
	)
