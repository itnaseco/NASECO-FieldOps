import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from naseco_fieldopsbackend.seed_configuration import validate_seed_scope

from naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.outgrower_pricing_policy.outgrower_pricing_policy import (
	require_policy_approver,
)


class ProductionContractTemplate(Document):
	def validate(self):
		validate_seed_scope(self.production_category, self.seed_class)
		if self.effective_from and self.effective_to and getdate(self.effective_from) > getdate(self.effective_to):
			frappe.throw(_("Effective From cannot be after Effective To."))
		if self.pricing_policy:
			policy = frappe.db.get_value(
				"Outgrower Pricing Policy",
				self.pricing_policy,
				["season", "crop", "production_category", "seed_class", "docstatus", "status"],
				as_dict=True,
			)
			if not policy or policy.docstatus != 1 or policy.status != "Active":
				frappe.throw(_("Pricing Policy must be submitted and active."))
			for fieldname in ("season", "crop", "production_category", "seed_class"):
				if self.get(fieldname) != policy.get(fieldname):
					frappe.throw(
						_("Template {0} must match the selected Pricing Policy.").format(
							self.meta.get_label(fieldname)
						)
					)

	def before_submit(self):
		require_policy_approver()
		self.validate_single_active_template()
		self.status = "Active"
		self.approved_by = frappe.session.user

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def validate_single_active_template(self):
		existing = frappe.db.get_value(
			"Production Contract Template",
			{
				"season": self.season,
				"crop": self.crop,
				"production_category": self.production_category,
				"seed_class": self.seed_class,
				"docstatus": 1,
				"status": "Active",
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("Active contract template {0} already covers this scope.").format(
					frappe.bold(existing)
				)
			)
