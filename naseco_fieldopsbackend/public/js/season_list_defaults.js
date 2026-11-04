// Navigation only: native removable filters, never permissions or sync scope.
frappe.provide("naseco_fieldops");
naseco_fieldops.setup_season_list_defaults = function (listview) {
	if (listview.__season_defaults_setup) return;
	listview.__season_defaults_setup = true;
	const route = frappe.get_route().join("/");
	const hasExplicitContext = () =>
		Object.keys(frappe.route_options || {}).length > 0 ||
		Boolean(window.location.search) || listview.filter_area.get().length > 0;
	const initiallyExplicit = hasExplicitContext();
	let userSelected = false;
	const load = () => frappe.call({
		method: "naseco_fieldopsbackend.season_list_context.get_active_seasons"
	}).then(r => r.message || []);
	const apply = season => listview.filter_area.add([[listview.doctype, "season", "=", season]]);
	listview.page.add_inner_button(__("All Seasons"), async () => {
		userSelected = true;
		await listview.filter_area.remove("season");
		listview.refresh();
	});
	listview.page.add_inner_button(__("Active Season"), async () => {
		userSelected = true;
		const seasons = await load();
		if (!seasons.length) return frappe.msgprint(__("No ongoing season with an active production plan is available. Choose a Season using the standard filters."));
		const choose = async season => {
			await listview.filter_area.remove("season");
			await apply(season);
		};
		if (seasons.length === 1) return choose(seasons[0].name);
		frappe.prompt({
			fieldname: "season", label: __("Season"), fieldtype: "Select", reqd: 1,
			options: seasons.map(s => ({ label: s.season_name || s.name, value: s.name }))
		}, values => choose(values.season), __("Select Active Season"));
	});
	// Do not overwrite route/saved filters, user edits, or a different page after
	// the asynchronous lookup. Once removed, never reapply on list refresh.
	if (!initiallyExplicit) load().then(seasons => {
		if (userSelected || frappe.get_route().join("/") !== route || hasExplicitContext()) return;
		if (seasons.length === 1) return apply(seasons[0].name);
	}).catch(() => { /* A failed suggestion must not block ordinary list access. */ });
};
