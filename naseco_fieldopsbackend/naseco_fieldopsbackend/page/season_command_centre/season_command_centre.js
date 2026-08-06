frappe.pages['season-command-centre'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Season Command Centre'),
		single_column: true
	});
	const state = { page, wrapper, plan: frappe.route_options?.plan || null };
	frappe.route_options = null;
	page.add_field({
		fieldname: 'season',
		label: __('Season'),
		fieldtype: 'Link',
		options: 'Season',
		change() {
			load_command_centre(state, this.get_value());
		}
	});
	page.set_primary_action(__('Refresh'), () => load_command_centre(state), 'refresh');
	$(wrapper).find('.layout-main-section').html('<div class="season-command-centre"></div>');
	load_command_centre(state);
};

function load_command_centre(state, season) {
	frappe.call({
		method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.page.season_command_centre.season_command_centre.get_command_centre',
		args: { plan: state.plan, season },
		freeze: true,
		callback(r) {
			const data = r.message || {};
			state.plan = data.plan && data.plan.name;
			render_command_centre(state, data);
		}
	});
}

function render_command_centre(state, data) {
	const root = $(state.wrapper).find('.season-command-centre');
	if (!data.plan) {
		root.html(`<div class="cc-empty">${escape_html(data.message || __('No production plan found.'))}</div>`);
		return;
	}
	const p = data.plan;
	state.page.set_title_sub(`${p.season} · ${p.company}`);
	state.page.clear_inner_toolbar();
	state.page.add_inner_button(__('Open Production Plan'), () => {
		frappe.set_route('Form', 'Season Production Plan', p.name);
	});

	root.html(`
		<div class="cc-heading">
			<div>
				<h2>${escape_html(p.plan_title || p.name)}</h2>
				<div class="text-muted">${escape_html(p.season)} · ${escape_html(p.calendar_status || '')}</div>
			</div>
			<span class="indicator-pill ${status_color(p.status)}">${escape_html(p.status)}</span>
		</div>
		<div class="cc-metrics">
			${metric(__('Readiness'), p.readiness_score, '%')}
			${metric(__('Contracted Hectares'), p.contracted_hectares, '', p.target_hectares)}
			${metric(__('Planted Hectares'), p.planted_hectares, '', p.target_hectares)}
			${metric(__('Production Forecast'), p.forecast_production_qty, ' kg', p.planned_production_qty)}
			${metric(__('QA Coverage'), p.qa_coverage_percent, '%')}
			${currency_metric(__('Current Exposure'), p.current_exposure_value)}
			${currency_metric(__('Assessed Harvest'), p.assessed_harvest_value)}
			${currency_metric(__('Settled Payable'), p.settled_net_payable)}
		</div>
		<div class="cc-grid">
			${panel(__('Crop Stage Progress'), table(
				[__('Stage'), __('Crop Cycles'), __('Hectares')],
				(data.stages || []).map(row => [
					row.stage, format_number(row.crop_cycles), format_number(row.hectares, null, 2)
				])
			))}
			${panel(__('Quality Assurance'), table(
				[__('Status'), __('Inspections'), __('Farmer %'), __('Supervisor %'), __('Spacing %'), __('GPS m')],
				(data.quality || []).map(row => [
					row.status, format_number(row.inspection_count),
					format_number(row.farmer_compliance, null, 1),
					format_number(row.supervisor_compliance, null, 1),
					format_number(row.spacing_compliance, null, 1),
					format_number(row.gps_accuracy, null, 1)
				])
			))}
			${panel(__('Exposure by Region'), table(
				[__('Region'), __('Cycles'), __('Stock Inputs'), __('Cash Advances'), __('Exposure')],
				(data.exposure || []).map(row => [
					row.region, format_number(row.crop_cycles),
					format_currency(row.stock_inputs), format_currency(row.cash_advances),
					format_currency(row.total_exposure)
				])
			))}
			${panel(__('Readiness Controls'), table(
				[__('Area'), __('Owner'), __('Status')],
				(data.readiness || []).map(row => [
					row.readiness_area, row.responsible_user || '-', row.status
				])
			))}
			${panel(__('Season Milestones'), table(
				[__('Milestone'), __('Planned End'), __('Status')],
				(data.milestones || []).map(row => [
					row.milestone, frappe.datetime.str_to_user(row.planned_end_date), row.status
				])
			))}
			${panel(__('Management Reports'), `
				<div class="cc-report-list">
					${(data.reports || []).map(report => `
						<button class="btn btn-default btn-sm cc-report" data-report="${escape_html(report)}">
							${escape_html(report)}
						</button>
					`).join('')}
				</div>
			`)}
		</div>
	`);
	root.find('.cc-report').on('click', function() {
		frappe.set_route('query-report', $(this).data('report'), { season: p.season, company: p.company });
	});
}

function metric(label, value, suffix = '', target = null) {
	const target_text = target === null || target === undefined
		? ''
		: `<div class="cc-target">${__('Target')} ${format_number(target, null, 1)}</div>`;
	return `<div class="cc-metric">
		<div class="cc-label">${escape_html(label)}</div>
		<div class="cc-value">${format_number(value || 0, null, 1)}${suffix}</div>
		${target_text}
	</div>`;
}

function currency_metric(label, value) {
	return `<div class="cc-metric">
		<div class="cc-label">${escape_html(label)}</div>
		<div class="cc-value cc-currency">${format_currency(value || 0)}</div>
	</div>`;
}

function panel(title, content) {
	return `<section class="cc-panel"><h3>${escape_html(title)}</h3>${content}</section>`;
}

function table(headers, rows) {
	return `<div class="table-responsive"><table class="table table-hover">
		<thead><tr>${headers.map(h => `<th>${escape_html(h)}</th>`).join('')}</tr></thead>
		<tbody>${rows.length ? rows.map(row => `<tr>${row.map(value => `<td>${escape_html(value ?? '-')}</td>`).join('')}</tr>`).join('') : `<tr><td colspan="${headers.length}" class="text-muted">${__('No records')}</td></tr>`}</tbody>
	</table></div>`;
}

function status_color(status) {
	if (['Active', 'Approved', 'Closed'].includes(status)) return 'green';
	if (['Awaiting Approval', 'Under Review', 'Closing'].includes(status)) return 'orange';
	if (status === 'Cancelled') return 'red';
	return 'gray';
}

function escape_html(value) {
	return frappe.utils.escape_html(String(value ?? ''));
}
