frappe.query_reports["Crop Cycle Financial Exposure"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "status",
			label: __("Crop Cycle Status"),
			fieldtype: "Select",
			options: "\nPLANNED\nACTIVE\nCOMPLETED",
			default: "ACTIVE",
		},
	],
};
