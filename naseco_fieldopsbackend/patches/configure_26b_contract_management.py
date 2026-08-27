import frappe

from naseco_fieldopsbackend.fieldops_finance import (
	ensure_finance_reference_data,
	setup_outgrower_finance,
)
from naseco_fieldopsbackend.fixtures.seed_data import (
	seed_26b_contract_reference_data,
)
from naseco_fieldopsbackend.patches.configure_seed_classification import (
	execute as ensure_seed_classification,
)


def execute():
	ensure_seed_classification()
	setup_outgrower_finance()
	ensure_finance_reference_data()
	seed_26b_contract_reference_data()
	backfill_outgrower_bank_accounts()


def backfill_outgrower_bank_accounts():
	for outgrower in frappe.get_all(
		"Outgrower",
		filters={"supplier": ["is", "set"], "default_bank_account": ["is", "not set"]},
		fields=["name", "supplier"],
	):
		bank_account = frappe.db.get_value(
			"Supplier",
			outgrower.supplier,
			"default_bank_account",
		)
		if bank_account:
			frappe.db.set_value(
				"Outgrower",
				outgrower.name,
				"default_bank_account",
				bank_account,
				update_modified=False,
			)
