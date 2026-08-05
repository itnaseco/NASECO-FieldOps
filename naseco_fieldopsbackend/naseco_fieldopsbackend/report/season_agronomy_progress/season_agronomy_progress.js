frappe.query_reports["Season Agronomy Progress"] = {
	filters: [
		{fieldname: "season", label: __("Season"), fieldtype: "Link", options: "Season"},
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company")}
	]
};
