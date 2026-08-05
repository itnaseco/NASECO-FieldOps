# Copyright (c) 2026, Naseco and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, now_datetime

from naseco_fieldopsbackend.roles import OUTGROWER_SUPERVISOR_ROLE


class Outgrower(Document):
	def before_validate(self):
		if self.supplier and not self.default_bank_account:
			self.default_bank_account = frappe.db.get_value(
				"Supplier", self.supplier, "default_bank_account"
			)

	def validate(self):
		self.validate_assigned_supervisor()
		self.validate_supplier_link()
		self.validate_bank_account()

	def before_save(self):
		"""Auto-calculate years since registration and farmer status"""
		if self.registration_date:
			self.calculate_years_since_registration()
			self.update_farmer_status()

	def after_insert(self):
		from naseco_fieldopsbackend.fieldops_finance import create_or_get_outgrower_supplier

		create_or_get_outgrower_supplier(self)

	def calculate_years_since_registration(self):
		"""Calculate years since registration date"""
		registration_date = getdate(self.registration_date)
		current_date = getdate(now_datetime())

		# Calculate the difference in years
		years = (current_date - registration_date).days / 365.25

		self.years_since_registration = round(years, 1)

	def update_farmer_status(self):
		"""Update farmer status based on years since registration"""
		years = self.years_since_registration or 0

		if years < 1:
			self.farmer_status = "Beginner"
		elif years < 2:
			self.farmer_status = "Intermediate"
		elif years < 5:
			self.farmer_status = "Experienced"
		else:
			self.farmer_status = "Expert"

	def validate_assigned_supervisor(self):
		if not self.assigned_supervisor:
			return

		user = frappe.db.get_value(
			"User",
			self.assigned_supervisor,
			["enabled", "user_type"],
			as_dict=True,
		)
		if not user or not cint(user.enabled) or user.user_type != "System User":
			frappe.throw(
				_("Assigned Supervisor must be an enabled System User."),
				title=_("Invalid Outgrower Supervisor"),
			)

		if not frappe.db.exists(
			"Has Role",
			{
				"parent": self.assigned_supervisor,
				"parenttype": "User",
				"role": OUTGROWER_SUPERVISOR_ROLE,
			},
		):
			frappe.throw(
				_("User {0} does not have the {1} role.").format(
					frappe.bold(self.assigned_supervisor),
					frappe.bold(OUTGROWER_SUPERVISOR_ROLE),
				),
				title=_("Invalid Outgrower Supervisor"),
			)

	def validate_supplier_link(self):
		if not self.supplier:
			return
		linked_outgrower = frappe.db.get_value("Supplier", self.supplier, "custom_outgrower")
		if linked_outgrower and linked_outgrower != self.name:
			frappe.throw(
				_("Supplier {0} is already linked to Outgrower {1}.").format(
					frappe.bold(self.supplier),
					frappe.bold(linked_outgrower),
				),
				title=_("Supplier Already Linked"),
			)

	def validate_bank_account(self):
		if not self.default_bank_account:
			return
		account = frappe.db.get_value(
			"Bank Account",
			self.default_bank_account,
			["party_type", "party", "disabled"],
			as_dict=True,
		)
		if (
			not account
			or account.disabled
			or account.party_type != "Supplier"
			or account.party != self.supplier
		):
			frappe.throw(
				_("Bank Account must be an enabled ERPNext Bank Account belonging to Supplier {0}.").format(
					frappe.bold(self.supplier)
				)
			)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def outgrower_supervisor_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql(
		"""
		select distinct
			user.name,
			user.full_name
		from `tabUser` user
		inner join `tabHas Role` user_role
			on user_role.parent = user.name
			and user_role.parenttype = 'User'
			and user_role.role = %(role)s
		where user.enabled = 1
			and user.user_type = 'System User'
			and (
				user.name like %(txt)s
				or coalesce(user.full_name, '') like %(txt)s
			)
		order by user.full_name asc, user.name asc
		limit %(start)s, %(page_len)s
		""",
		{
			"role": OUTGROWER_SUPERVISOR_ROLE,
			"txt": f"%{txt}%",
			"start": cint(start),
			"page_len": cint(page_len),
		},
	)
