import frappe


LEGACY_PROTOCOL = "Legacy Percentage V1"
COUNT_PROTOCOL = "Cumulative Counts V2"
COUNT_PARAMETERS = {
	"OFFTYPES_FEMALE",
	"OFFTYPES_MALE",
	"VOLUNTEERS",
	"LATE_MATURERS",
	"DISEASED_PLANTS",
	"NOXIOUS_WEEDS",
	"FEMALES_SHEDDING_POLLEN",
}
INSPECTION_PARAMETERS = {"ISOLATION_DISTANCE", "TIME_ISOLATION"}


def execute():
	classify_existing_inspections()
	configure_parameters()
	configure_standards()


def classify_existing_inspections():
	frappe.db.sql(
		"""
		update `tabInspection` inspection
		set inspection.sampling_protocol_version = %s
		where exists (
			select 1
			from `tabInspection Take Result` reading
			where reading.parent = inspection.name
				and reading.parenttype = 'Inspection'
		)
		""",
		LEGACY_PROTOCOL,
	)
	frappe.db.sql(
		"""
		update `tabInspection` inspection
		set inspection.sampling_protocol_version = %s
		where not exists (
			select 1
			from `tabInspection Take Result` reading
			where reading.parent = inspection.name
				and reading.parenttype = 'Inspection'
		)
		""",
		COUNT_PROTOCOL,
	)


def configure_parameters():
	for parameter in frappe.get_all(
		"Inspection Parameter",
		fields=["name", "parameter_code"],
	):
		if parameter.parameter_code in COUNT_PARAMETERS:
			frappe.db.set_value(
				"Inspection Parameter",
				parameter.name,
				{
					"data_type": "Count",
					"unit": "Nos",
					"measurement_scope": "Inspection Take",
					"calculation_method": "Cumulative Incidence",
					"denominator_basis": "Total Plants Counted",
					"requires_take_counts": 1,
				},
				update_modified=False,
			)
		elif parameter.parameter_code in INSPECTION_PARAMETERS:
			frappe.db.set_value(
				"Inspection Parameter",
				parameter.name,
				{
					"measurement_scope": "Inspection",
					"calculation_method": "Direct Value",
					"denominator_basis": None,
					"requires_take_counts": 0,
				},
				update_modified=False,
			)
		else:
			frappe.db.set_value(
				"Inspection Parameter",
				parameter.name,
				{
					"measurement_scope": "Inspection Take",
					"calculation_method": "Direct Value",
					"denominator_basis": None,
				},
				update_modified=False,
			)


def configure_standards():
	parameter_names = frappe.get_all(
		"Inspection Parameter",
		filters={"parameter_code": ["in", list(COUNT_PARAMETERS)]},
		pluck="name",
	)
	if not parameter_names:
		return
	frappe.db.set_value(
		"Inspection Standard",
		{"parameter": ["in", parameter_names]},
		{
			"aggregation_method": "Cumulative Incidence",
			"unit": "Nos",
		},
		update_modified=False,
	)
