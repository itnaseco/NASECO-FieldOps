// Copyright (c) 2026, NASECO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Inspection', {
	refresh(frm) {
		frm.set_query('assigned_to', () => ({
			query: 'naseco_fieldopsbackend.roles.user_with_role_query',
			filters: { role: 'Quality Inspector' }
		}));
		set_completed_inspection_read_only(frm);
		show_take_progress(frm);

		if (frm.doc.farmer_compliance_status) {
			frm.dashboard.add_indicator(
				__('Farmer: {0}% {1}', [frm.doc.farmer_compliance_percent || 0, frm.doc.farmer_compliance_status]),
				compliance_color(frm.doc.farmer_compliance_status)
			);
		}
		if (frm.doc.supervisor_compliance_status) {
			frm.dashboard.add_indicator(
				__('Supervisor: {0}% {1}', [frm.doc.supervisor_compliance_percent || 0, frm.doc.supervisor_compliance_status]),
				compliance_color(frm.doc.supervisor_compliance_status)
			);
		}
		if (frm.doc.inspection_quality_score) {
			frm.dashboard.add_indicator(
				__('Inspection Quality: {0}', [frm.doc.inspection_quality_score]),
				quality_color(frm.doc.inspection_quality_score)
			);
		}
		if ((frm.doc.takes || []).length) {
			frm.add_custom_button(
				__('View Inspection Takes'),
				() => show_inspection_takes(frm),
				__('Actions')
			);
		}
		if (!frm.is_new()) {
			add_quality_review_actions(frm);
			if (!is_inspection_locked(frm)) {
				add_inspection_controls_action(frm);
				add_inspection_take_action(frm);
			}

			frm.add_custom_button(__('View Corrective Actions'), () => {
				frappe.set_route('List', 'Field Corrective Action', { inspection: frm.doc.name });
			}, __('Navigate'));
			if (frm.doc.crop_cycle) {
				frm.add_custom_button(__('Open Crop Cycle'), () => {
					frappe.set_route('Form', 'Crop Cycle', frm.doc.crop_cycle);
				}, __('Navigate'));
			}
		}
	}
});

function set_completed_inspection_read_only(frm) {
	if (!is_inspection_locked(frm)) {
		frm.set_intro(null);
		return;
	}

	frm.set_read_only();
	const is_verified = frm.doc.status === 'Verified';
	const is_reinspection = frm.doc.status === 'Reinspection Required';
	const color = is_verified ? 'green' : is_reinspection ? 'red' : 'orange';
	const message = is_verified
		? __('This inspection has been verified by Quality Assurance. Its evidence and results are final.')
		: is_reinspection
			? __('Quality Assurance has required a reinspection. The original evidence remains locked.')
			: __('All required takes are complete. This inspection is locked while it awaits Quality Manager review.');
	frm.set_intro(
		`${message} ${__('Completed on {0}.', [format_take_datetime(frm.doc.completed_at)])}`,
		color
	);
	frm.dashboard.add_indicator(__(frm.doc.status), color);
}

function is_inspection_locked(frm) {
	return ['Awaiting QA Review', 'Verified', 'Reinspection Required'].includes(frm.doc.status);
}

function add_quality_review_actions(frm) {
	if (frm.doc.status !== 'Awaiting QA Review' || !frappe.user.has_role('Quality Manager')) return;

	frm.add_custom_button(
		__('Verify Inspection'),
		() => review_inspection(frm, 'Verified'),
		__('QA Review')
	);
	frm.add_custom_button(
		__('Require Reinspection'),
		() => review_inspection(frm, 'Reinspection Required'),
		__('QA Review')
	);
}

function review_inspection(frm, decision) {
	const dialog = new frappe.ui.Dialog({
		title: __(decision),
		fields: [{
			fieldname: 'notes',
			fieldtype: 'Small Text',
			label: __('QA Review Notes'),
			reqd: decision === 'Reinspection Required'
		}],
		primary_action_label: __(decision),
		primary_action(values) {
			frappe.call({
				method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection.review_inspection',
				args: {
					inspection: frm.doc.name,
					decision,
					notes: values.notes
				},
				freeze: true,
				callback(r) {
					dialog.hide();
					const result = r.message || {};
					if (result.reinspection) {
						frappe.show_alert({
							message: __('Reinspection {0} created', [result.reinspection]),
							indicator: 'orange'
						});
					}
					frm.reload_doc();
				}
			});
		}
	});
	dialog.show();
}

function show_take_progress(frm) {
	const completed = get_completed_take_count(frm);
	const required = get_required_take_count(frm);
	const color = required && completed >= required ? 'green' : completed > 0 ? 'orange' : 'red';

	frm.dashboard.add_indicator(
		__('Inspection Takes: {0} / {1}', [completed, required || 0]),
		color
	);
}

function add_inspection_take_action(frm) {
	if (!['Scheduled', 'In Progress'].includes(frm.doc.status)) return;

	const completed = get_completed_take_count(frm);
	const required = get_required_take_count(frm);
	const is_complete = required > 0 && completed >= required;

	if (is_complete) {
		const button = frm.add_custom_button(__('Add Inspection Take'), () => {}, __('Actions'));
		button.prop('disabled', true);
		button.attr('title', __('All required inspection takes have been completed.'));
		return;
	}

	frm.add_custom_button(__('Add Inspection Take'), () => show_add_take_dialog(frm), __('Actions'));
}

function add_inspection_controls_action(frm) {
	if (frm.doc.sampling_protocol_version !== 'Cumulative Counts V2') return;
	if (!['Scheduled', 'In Progress'].includes(frm.doc.status)) return;
	const label = frm.doc.controls_completed
		? __('Update Inspection Controls')
		: __('Record Inspection Controls');
	frm.add_custom_button(label, () => show_inspection_controls_dialog(frm), __('Actions'));
}

function show_inspection_controls_dialog(frm) {
	frappe.call({
		method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection.get_inspection_control_schema',
		args: { inspection: frm.doc.name },
		freeze: true,
		freeze_message: __('Loading inspection-level controls...'),
		callback(r) {
			const schema = r.message || {};
			if (!(schema.controls || []).length) {
				frappe.msgprint(__('No inspection-level controls are configured for this inspection.'));
				return;
			}
			build_inspection_controls_dialog(frm, schema);
		}
	});
}

function build_inspection_controls_dialog(frm, schema) {
	const fields = [];
	(schema.controls || []).forEach((control, index) => {
		fields.push({
			fieldname: `control_${index}`,
			fieldtype: get_attribute_fieldtype(control.data_type),
			label: control.unit
				? __('{0} ({1})', [control.label, control.unit])
				: __(control.label),
			options: control.data_type === 'Yes/No' ? '\nYes\nNo' : undefined,
			reqd: cint(control.mandatory),
			default: control.value,
			description: control.description
				? __('Responsible: {0}. {1}', [control.responsibility, control.description])
				: __('Responsible: {0}', [control.responsibility])
		});
		fields.push({
			fieldname: `control_remarks_${index}`,
			fieldtype: 'Small Text',
			label: __('{0} Remarks', [control.label]),
			default: control.remarks
		});
	});

	const dialog = new frappe.ui.Dialog({
		title: __('Inspection-Level Controls'),
		size: 'large',
		fields,
		primary_action_label: __('Save Controls'),
		primary_action(values) {
			const readings = (schema.controls || []).map((control, index) => ({
				parameter: control.parameter,
				value: values[`control_${index}`],
				remarks: values[`control_remarks_${index}`]
			}));
			frappe.call({
				method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection.save_inspection_controls',
				args: {
					inspection: frm.doc.name,
					readings: JSON.stringify(readings)
				},
				freeze: true,
				freeze_message: __('Evaluating inspection controls...'),
				callback() {
					dialog.hide();
					frappe.show_alert({ message: __('Inspection controls saved'), indicator: 'green' });
					frm.reload_doc();
				}
			});
		}
	});
	dialog.show();
}

function show_add_take_dialog(frm) {
	frappe.call({
		method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection.get_take_form_schema',
		args: { inspection: frm.doc.name },
		freeze: true,
		freeze_message: __('Loading inspection attributes...'),
		callback(r) {
			const schema = r.message || {};
			if (!(schema.attributes || []).length) {
				frappe.msgprint(__('No inspection attributes are configured for this inspection stage and production category.'));
				return;
			}
			build_take_dialog(frm, schema);
		}
	});
}

function build_take_dialog(frm, schema) {
	const attribute_fields = [];
	(schema.attributes || []).forEach((attribute, index) => {
		attribute_fields.push({
			fieldname: `attribute_${index}`,
			fieldtype: get_attribute_fieldtype(attribute.data_type),
			label: attribute.unit
				? __('{0} ({1})', [attribute.label, attribute.unit])
				: __(attribute.label),
			options: attribute.data_type === 'Yes/No' ? '\nYes\nNo' : undefined,
			reqd: cint(attribute.mandatory),
			default: attribute.default_value,
			precision: ['Number', 'Percent', 'Score'].includes(attribute.data_type) ? 4 : undefined,
			description: attribute.description
				? __('Responsible: {0}. {1}', [attribute.responsibility, attribute.description])
				: __('Responsible: {0}', [attribute.responsibility])
		});
	});

	let d;
	d = new frappe.ui.Dialog({
		title: __('Inspection Take {0}', [schema.next_take_number]),
		size: 'large',
		fields: [
			{
				fieldname: 'take_progress',
				fieldtype: 'HTML',
				options: `
					<div class="text-muted small" style="margin-bottom: 8px;">
						${__('Completed takes: {0} of {1}', [
							schema.completed_take_count || 0,
							schema.required_take_count || 0
						])}
					</div>
				`
			},
			{
				fieldname: 'captured_at',
				fieldtype: 'Datetime',
				label: __('Captured At'),
				read_only: 1
			},
			{
				fieldname: 'gps_status',
				fieldtype: 'HTML'
			},
			{
				fieldtype: 'Section Break',
				label: __('Automatically Captured Location')
			},
			{
				fieldname: 'latitude',
				fieldtype: 'Float',
				label: __('Latitude'),
				precision: 8,
				read_only: 1,
				reqd: 1
			},
			{
				fieldtype: 'Column Break'
			},
			{
				fieldname: 'longitude',
				fieldtype: 'Float',
				label: __('Longitude'),
				precision: 8,
				read_only: 1,
				reqd: 1
			},
			{
				fieldname: 'gps_accuracy_meters',
				fieldtype: 'Float',
				label: __('GPS Accuracy (m)'),
				read_only: 1
			},
			{
				fieldname: 'location_sample_count',
				fieldtype: 'Int',
				label: __('Stable GPS Samples'),
				read_only: 1
			},
			{
				fieldname: 'location_capture_duration_seconds',
				fieldtype: 'Float',
				label: __('Capture Duration (seconds)'),
				read_only: 1
			},
			{
				fieldname: 'location_source',
				fieldtype: 'Data',
				label: __('Location Source'),
				default: 'Web Geolocation',
				hidden: 1,
				read_only: 1
			},
			{
				fieldname: 'spacing_status',
				fieldtype: 'HTML'
			},
			...((schema.positioning || {}).can_override ? [
				{
					fieldtype: 'Section Break',
					label: __('Positioning Exception')
				},
				{
					fieldname: 'positioning_override',
					fieldtype: 'Check',
					label: __('Override Positioning Requirements'),
					description: __('The exception and approving user will be recorded.'),
					onchange() {
						update_take_save_state(d, schema);
					}
				},
				{
					fieldname: 'positioning_override_reason',
					fieldtype: 'Small Text',
					label: __('Override Reason'),
					depends_on: 'eval:doc.positioning_override',
					mandatory_depends_on: 'eval:doc.positioning_override',
					onchange() {
						update_take_save_state(d, schema);
					}
				}
			] : []),
				{
					fieldtype: 'Section Break',
					label: __('Inspection Attributes')
				},
				...(schema.requires_total_plants ? [{
					fieldname: 'total_plants_counted',
					fieldtype: 'Int',
					label: __('Total Plants Counted'),
					reqd: 1,
					description: __('Total crop plants physically counted at this take.')
				}] : []),
				...attribute_fields,
			{
				fieldtype: 'Section Break',
				label: __('Take Notes')
			},
			{
				fieldname: 'notes',
				fieldtype: 'Small Text',
				label: __('Notes')
			}
		],
		primary_action_label: __('Save Inspection Take'),
		primary_action(values) {
			save_inspection_take(frm, d, schema, values);
		}
	});

	d.show();
	d.get_primary_btn().prop('disabled', true);
	d.$wrapper.on('hidden.bs.modal', () => stop_take_location_capture(d));
	capture_take_location(d, schema);
}

function get_attribute_fieldtype(data_type) {
	if (data_type === 'Count') return 'Int';
	if (['Number', 'Percent', 'Score'].includes(data_type)) return 'Float';
	if (data_type === 'Date') return 'Date';
	if (data_type === 'Yes/No') return 'Select';
	if (data_type === 'Text') return 'Small Text';
	return 'Data';
}

function capture_take_location(dialog, schema) {
	stop_take_location_capture(dialog);
	const wrapper = dialog.fields_dict.gps_status.$wrapper;
	const positioning = schema.positioning || {};
	const timeout_seconds = cint(positioning.location_capture_timeout_seconds || 30);
	const state = {
		schema,
		positioning,
		started_at: Date.now(),
		samples: [],
		strict_ready: false,
		watch_id: null,
		timeout_id: null
	};
	dialog._take_location_capture = state;
	wrapper.html(`
		<div class="text-muted small" style="padding: 8px 0;">
			${__('Acquiring stable high-accuracy GPS fixes...')}
		</div>
	`);
	dialog.get_primary_btn().prop('disabled', true);

	if (!navigator.geolocation) {
		show_location_error(dialog, schema, __('Geolocation is not supported by this browser.'));
		return;
	}

	state.watch_id = navigator.geolocation.watchPosition(
		(position) => handle_take_location_sample(dialog, schema, position),
		(error) => {
			if (error.code !== error.TIMEOUT) {
				show_location_error(dialog, schema, get_location_error_message(error));
			}
		},
		{
			enableHighAccuracy: true,
			timeout: timeout_seconds * 1000,
			maximumAge: 0
		}
	);
	state.timeout_id = setTimeout(
		() => finish_take_location_timeout(dialog, schema),
		timeout_seconds * 1000
	);
}

function handle_take_location_sample(dialog, schema, position) {
	const state = dialog._take_location_capture;
	if (!state || !position || !position.coords) return;

	const sample = {
		latitude: flt(position.coords.latitude),
		longitude: flt(position.coords.longitude),
		accuracy: flt(position.coords.accuracy),
		timestamp: position.timestamp || Date.now()
	};
	if (
		!Number.isFinite(sample.latitude)
		|| !Number.isFinite(sample.longitude)
		|| !Number.isFinite(sample.accuracy)
		|| sample.accuracy <= 0
	) return;

	const recent_cutoff = Date.now() - 12000;
	state.samples = [...state.samples, sample]
		.filter((item) => item.timestamp >= recent_cutoff)
		.slice(-20);

	const maximum_accuracy = flt(state.positioning.maximum_gps_accuracy_m || 5);
	const stable_samples = state.samples.filter((item) => item.accuracy <= maximum_accuracy);
	const candidates = stable_samples.length ? stable_samples : state.samples;
	const best = candidates.reduce((selected, item) => {
		if (!selected || item.accuracy < selected.accuracy) return item;
		if (item.accuracy === selected.accuracy && item.timestamp > selected.timestamp) return item;
		return selected;
	}, null);
	if (!best) return;

	const elapsed_seconds = (Date.now() - state.started_at) / 1000;
	const spacing = get_take_spacing(schema.previous_take, best);
	const minimum_samples = cint(state.positioning.minimum_location_samples || 3);
	const spacing_is_valid = (
		spacing === null
		|| (
			spacing >= flt(state.positioning.minimum_take_spacing_m || 3)
			&& spacing <= flt(state.positioning.maximum_take_spacing_m || 7)
		)
	);
	state.strict_ready = (
		stable_samples.length >= minimum_samples
		&& best.accuracy <= maximum_accuracy
		&& spacing_is_valid
	);
	state.best = best;
	state.stable_sample_count = stable_samples.length;
	state.spacing = spacing;

	dialog.set_value('latitude', best.latitude);
	dialog.set_value('longitude', best.longitude);
	dialog.set_value('gps_accuracy_meters', best.accuracy);
	dialog.set_value('location_sample_count', stable_samples.length);
	dialog.set_value('location_capture_duration_seconds', elapsed_seconds);
	dialog.set_value('captured_at', frappe.datetime.obj_to_str(new Date(best.timestamp)));

	render_take_location_status(dialog, schema, false);
	update_take_save_state(dialog, schema);
	if (state.strict_ready) {
		stop_take_location_capture(dialog);
	}
}

function get_take_spacing(previous_take, current) {
	if (!previous_take) return null;
	return haversine_distance_m(
		flt(previous_take.latitude),
		flt(previous_take.longitude),
		current.latitude,
		current.longitude
	);
}

function haversine_distance_m(lat1, lon1, lat2, lon2) {
	const radius = 6371000;
	const to_radians = (value) => value * Math.PI / 180;
	const latitude_1 = to_radians(lat1);
	const latitude_2 = to_radians(lat2);
	const latitude_delta = to_radians(lat2 - lat1);
	const longitude_delta = to_radians(lon2 - lon1);
	const a = (
		Math.sin(latitude_delta / 2) ** 2
		+ Math.cos(latitude_1) * Math.cos(latitude_2) * Math.sin(longitude_delta / 2) ** 2
	);
	return radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function render_take_location_status(dialog, schema, timed_out) {
	const state = dialog._take_location_capture || {};
	const positioning = schema.positioning || {};
	const wrapper = dialog.fields_dict.gps_status.$wrapper;
	const spacing_wrapper = dialog.fields_dict.spacing_status.$wrapper;
	const best = state.best;
	if (!best) {
		wrapper.html(`
			<div class="text-danger small" style="padding: 8px 0;">
				${__('No usable GPS fix was obtained. Move to an open area and retry.')}
				<button type="button" class="btn btn-xs btn-default retry-location" style="margin-left: 8px;">
					${__('Retry GPS')}
				</button>
			</div>
		`);
		bind_take_location_retry(dialog, schema);
		return;
	}

	const preferred_accuracy = flt(positioning.preferred_gps_accuracy_m || 3);
	const maximum_accuracy = flt(positioning.maximum_gps_accuracy_m || 5);
	const minimum_samples = cint(positioning.minimum_location_samples || 3);
	const accuracy_color = best.accuracy <= preferred_accuracy
		? 'green'
		: best.accuracy <= maximum_accuracy ? 'orange' : 'red';
	const acquisition_label = state.strict_ready
		? __('Position ready')
		: timed_out ? __('GPS acquisition timed out') : __('Refining GPS position');

	wrapper.html(`
		<div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 8px 0;">
			<span class="indicator-pill ${accuracy_color}">
				${escape_take_value(acquisition_label)}
			</span>
			<span class="small">
				${__('Accuracy: {0}', [format_take_number(best.accuracy, 1, 'm')])}
			</span>
			<span class="small">
				${__('Stable samples: {0}/{1}', [state.stable_sample_count || 0, minimum_samples])}
			</span>
			${timed_out ? `
				<button type="button" class="btn btn-xs btn-default retry-location">
					${__('Retry GPS')}
				</button>
			` : ''}
		</div>
	`);
	if (timed_out) bind_take_location_retry(dialog, schema);

	spacing_wrapper.html(build_spacing_guidance(state.spacing, positioning));
}

function build_spacing_guidance(spacing, positioning) {
	if (spacing === null || spacing === undefined) {
		return `
			<div class="indicator-pill green" style="margin: 8px 0;">
				${__('First take: spacing starts from the next take.')}
			</div>
		`;
	}

	const minimum = flt(positioning.minimum_take_spacing_m || 3);
	const maximum = flt(positioning.maximum_take_spacing_m || 7);
	const target = flt(positioning.target_take_spacing_m || 5);
	let color = 'green';
	let message = __('Spacing {0} m: within the {1}-{2} m standard.', [
		format_number(spacing, null, 1),
		format_number(minimum, null, 1),
		format_number(maximum, null, 1)
	]);
	if (spacing < minimum) {
		color = 'red';
		message = __('Spacing {0} m: move at least {1} m farther from the previous take.', [
			format_number(spacing, null, 1),
			format_number(minimum - spacing, null, 1)
		]);
	} else if (spacing > maximum) {
		color = 'red';
		message = __('Spacing {0} m: move at least {1} m closer to the previous take.', [
			format_number(spacing, null, 1),
			format_number(spacing - maximum, null, 1)
		]);
	}
	return `
		<div class="indicator-pill ${color}" style="margin: 8px 0;">
			${escape_take_value(message)}
		</div>
		<div class="text-muted small">
			${__('Target spacing: {0} m', [format_number(target, null, 1)])}
		</div>
	`;
}

function finish_take_location_timeout(dialog, schema) {
	const state = dialog._take_location_capture;
	if (!state || state.strict_ready) return;
	stop_take_location_capture(dialog);
	render_take_location_status(dialog, schema, true);
	update_take_save_state(dialog, schema);
}

function stop_take_location_capture(dialog) {
	const state = dialog._take_location_capture;
	if (!state) return;
	if (state.watch_id !== null && navigator.geolocation) {
		navigator.geolocation.clearWatch(state.watch_id);
		state.watch_id = null;
	}
	if (state.timeout_id) {
		clearTimeout(state.timeout_id);
		state.timeout_id = null;
	}
}

function update_take_save_state(dialog, schema) {
	const state = dialog._take_location_capture || {};
	const values = dialog.get_values(true) || {};
	const override_requested = cint(values.positioning_override);
	const override_ready = (
		cint((schema.positioning || {}).can_override)
		&& override_requested
		&& String(values.positioning_override_reason || '').trim()
	);
	const has_location = values.latitude !== null
		&& values.latitude !== undefined
		&& values.longitude !== null
		&& values.longitude !== undefined
		&& flt(values.gps_accuracy_meters) > 0;
	const can_save = has_location && (
		override_requested ? override_ready : state.strict_ready
	);
	dialog.get_primary_btn().prop('disabled', !can_save);
}

function bind_take_location_retry(dialog, schema) {
	dialog.fields_dict.gps_status.$wrapper.find('.retry-location').on(
		'click',
		() => capture_take_location(dialog, schema)
	);
}

function show_location_error(dialog, schema, message) {
	stop_take_location_capture(dialog);
	const wrapper = dialog.fields_dict.gps_status.$wrapper;
	wrapper.html(`
		<div class="text-danger small" style="padding: 8px 0;">
			${frappe.utils.escape_html(message)}
			<button type="button" class="btn btn-xs btn-default retry-location" style="margin-left: 8px;">
				${__('Retry GPS')}
			</button>
		</div>
	`);
	bind_take_location_retry(dialog, schema);
	dialog.get_primary_btn().prop('disabled', true);
}

function get_location_error_message(error) {
	if (error.code === error.PERMISSION_DENIED) {
		return __('Location permission was denied. Enable it for this site and retry.');
	}
	if (error.code === error.POSITION_UNAVAILABLE) {
		return __('The device could not determine its current location.');
	}
	if (error.code === error.TIMEOUT) {
		return __('GPS capture timed out. Move to an open area and retry.');
	}
	return __('Unable to capture the current GPS location.');
}

function save_inspection_take(frm, dialog, schema, values) {
	const readings = (schema.attributes || []).map((attribute, index) => ({
		parameter: attribute.parameter,
		value: values[`attribute_${index}`]
	}));

	dialog.get_primary_btn().prop('disabled', true);
	stop_take_location_capture(dialog);
	frappe.call({
		method: 'naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.inspection.inspection.add_inspection_take',
		args: {
			inspection: frm.doc.name,
			total_plants_counted: values.total_plants_counted,
			latitude: values.latitude,
			longitude: values.longitude,
			gps_accuracy_meters: values.gps_accuracy_meters,
			captured_at: values.captured_at,
			location_sample_count: values.location_sample_count,
			location_capture_duration_seconds: values.location_capture_duration_seconds,
			location_source: values.location_source,
			positioning_override: values.positioning_override,
			positioning_override_reason: values.positioning_override_reason,
			notes: values.notes,
			readings: JSON.stringify(readings)
		},
		freeze: true,
		freeze_message: __('Evaluating and aggregating take results...'),
		callback(r) {
			const result = r.message || {};
			dialog.hide();
			frappe.show_alert({
				message: result.status === 'Awaiting QA Review'
					? __('Inspection Take {0} saved; Inspection sent for QA review', [result.take_number])
					: __('Inspection Take {0} saved', [result.take_number]),
				indicator: 'green'
			});
			frm.reload_doc();
		},
		error() {
			update_take_save_state(dialog, schema);
		}
	});
}

function get_required_take_count(frm) {
	return cint(frm.doc.required_take_count || 0);
}

function get_completed_take_count(frm) {
	return cint(frm.doc.completed_take_count || 0);
}

function compliance_color(status) {
	if (status === 'Compliant') return 'green';
	if (status === 'Improvements Required') return 'orange';
	return 'red';
}

function quality_color(status) {
	if (status === 'Good') return 'green';
	if (status === 'Acceptable') return 'orange';
	return 'red';
}

function show_inspection_takes(frm) {
	const takes = [...(frm.doc.takes || [])].sort(
		(a, b) => cint(a.take_number || a.idx) - cint(b.take_number || b.idx)
	);
	if (!takes.length) {
		frappe.msgprint(__('No Inspection Takes have been captured.'));
		return;
	}

	let geojson = { type: 'FeatureCollection', features: [] };
	try {
		geojson = JSON.parse(frm.doc.inspection_map_geojson || '{"type":"FeatureCollection","features":[]}');
	} catch (error) {
		console.warn('Invalid Inspection map GeoJSON', error);
	}

	const map_id = `inspection_take_map_${Date.now()}`;
	const take_rows = takes.map((take) => {
		const take_number = cint(take.take_number || take.idx);
		const latitude = flt(take.latitude);
		const longitude = flt(take.longitude);
		const is_inside = cint(take.inside_plot_boundary) === 1;
		const is_complete = take.take_status === 'Complete';
		const gps_quality = take.gps_quality_status || 'Poor';
		const spacing_status = take.spacing_status || '-';
		const spacing_color = spacing_status === 'Within Standard' || spacing_status === 'First Take'
			? 'green'
			: 'red';
		return `
			<tr>
				<td>
					<button type="button" class="btn btn-link btn-sm focus-take"
						data-take-number="${take_number}" style="padding: 0;">
						${__('Take {0}', [take_number])}
					</button>
				</td>
				<td>
					<div style="font-family: monospace;">${latitude.toFixed(8)}</div>
					<div style="font-family: monospace;">${longitude.toFixed(8)}</div>
					<a href="https://www.openstreetmap.org/?mlat=${encodeURIComponent(latitude)}&mlon=${encodeURIComponent(longitude)}#map=18/${encodeURIComponent(latitude)}/${encodeURIComponent(longitude)}"
						target="_blank" rel="noopener noreferrer" class="small">
						${__('Open location')}
					</a>
				</td>
				<td>
					<div>${format_take_number(take.gps_accuracy_meters, 1, 'm')}</div>
					<span class="indicator-pill ${quality_color(gps_quality)}">${escape_take_value(gps_quality)}</span>
				</td>
				<td>
					<div>${escape_take_value(format_take_datetime(take.captured_at))}</div>
					<div class="text-muted small">${escape_take_value(take.captured_by || '-')}</div>
				</td>
				<td>${cint(take.attribute_count || 0)}</td>
				<td>
					<span class="indicator-pill ${is_inside ? 'green' : 'red'}">
						${is_inside ? __('Inside') : __('Outside')}
					</span>
				</td>
				<td>
					<div>${format_take_number(take.distance_from_previous_take_m, 1, 'm')}</div>
					<span class="indicator-pill ${spacing_color}">${escape_take_value(spacing_status)}</span>
				</td>
				<td>
					${cint(take.positioning_override)
						? `<span class="indicator-pill orange">${__('Overridden')}</span>
							<div class="text-muted small">${escape_take_value(take.positioning_override_reason || '')}</div>`
						: '-'}
				</td>
				<td>
					<span class="indicator-pill ${is_complete ? 'green' : 'orange'}">
						${escape_take_value(take.take_status || __('Incomplete'))}
					</span>
				</td>
			</tr>
		`;
	}).join('');

	let d = new frappe.ui.Dialog({
		title: __('Inspection Takes: {0}', [frm.doc.inspection_id || frm.doc.name]),
		size: 'extra-large',
		fields: [{ fieldtype: 'HTML', fieldname: 'takes_html' }]
	});
	d.fields_dict.takes_html.$wrapper.html(`
		<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 16px; padding: 4px 0 14px; border-bottom: 1px solid var(--border-color);">
			<div><div class="text-muted small">${__('Completed Takes')}</div><strong>${frm.doc.completed_take_count || 0} / ${frm.doc.required_take_count || 0}</strong></div>
			<div><div class="text-muted small">${__('Spacing Standard')}</div><strong>${format_take_number(frm.doc.target_take_spacing_m, 1, 'm')}</strong></div>
			<div><div class="text-muted small">${__('Average Spacing')}</div><strong>${format_take_number(frm.doc.average_take_spacing_m, 1, 'm')}</strong></div>
			<div><div class="text-muted small">${__('Median Spacing')}</div><strong>${format_take_number(frm.doc.median_take_spacing_m, 1, 'm')}</strong></div>
			<div><div class="text-muted small">${__('Spacing Compliance')}</div><strong>${format_take_number(frm.doc.spacing_compliance_percent, 1, '%')}</strong></div>
			<div><div class="text-muted small">${__('Average GPS Accuracy')}</div><strong>${format_take_number(frm.doc.average_gps_accuracy_m, 1, 'm')}</strong></div>
			<div><div class="text-muted small">${__('Worst GPS Accuracy')}</div><strong>${format_take_number(frm.doc.worst_gps_accuracy_m, 1, 'm')}</strong></div>
			<div><div class="text-muted small">${__('Positioning Overrides')}</div><strong>${frm.doc.positioning_override_count || 0}</strong></div>
			<div><div class="text-muted small">${__('Total Path')}</div><strong>${format_take_number(frm.doc.total_take_path_distance_m, 1, 'm')}</strong></div>
			<div><div class="text-muted small">${__('Outside Plot')}</div><strong>${frm.doc.takes_outside_plot || 0}</strong></div>
			<div><div class="text-muted small">${__('Inspection Quality')}</div><strong>${escape_take_value(frm.doc.inspection_quality_score || '-')}</strong></div>
		</div>
		<section style="margin-top: 16px;">
			<div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 8px;">
				<h5 style="margin: 0;">${__('Inspection Take Locations')}</h5>
				<div class="text-muted small" style="display: flex; gap: 14px; flex-wrap: wrap;">
					<span><span style="color: #16a34a;">&#9679;</span> ${__('Inside plot')}</span>
					<span><span style="color: #dc2626;">&#9679;</span> ${__('Outside plot')}</span>
					<span><span style="display: inline-block; width: 18px; border-top: 3px solid #16a34a; vertical-align: middle;"></span> ${__('Spacing compliant')}</span>
					<span><span style="display: inline-block; width: 18px; border-top: 3px solid #dc2626; vertical-align: middle;"></span> ${__('Spacing exception')}</span>
				</div>
			</div>
			<div id="${map_id}" role="img" aria-label="${__('Map of inspection take coordinates')}"
				style="height: 430px; width: 100%; border: 1px solid var(--border-color); z-index: 1;"></div>
		</section>
		<div class="table-responsive" style="margin-top: 16px;">
			<table class="table table-bordered table-hover" style="margin-bottom: 0;">
				<thead>
					<tr>
						<th>${__('Take')}</th>
						<th>${__('Coordinates')}</th>
						<th>${__('GPS Accuracy')}</th>
						<th>${__('Captured')}</th>
						<th>${__('Attributes')}</th>
						<th>${__('Boundary')}</th>
						<th>${__('Spacing')}</th>
						<th>${__('Override')}</th>
						<th>${__('Status')}</th>
					</tr>
				</thead>
				<tbody>${take_rows}</tbody>
			</table>
		</div>
	`);

	let rendered_map = null;
	d.$wrapper.one('shown.bs.modal', () => {
		load_leaflet(() => {
			try {
				rendered_map = render_inspection_take_map(frm, d, takes, geojson, map_id);
				d.fields_dict.takes_html.$wrapper.find('.focus-take').on('click', function() {
					const take_number = cint($(this).data('take-number'));
					const marker = rendered_map.markers[take_number];
					if (marker) {
						rendered_map.map.setView(marker.getLatLng(), Math.max(rendered_map.map.getZoom(), 18));
						marker.openPopup();
					}
				});
			} catch (error) {
				console.error('Unable to render Inspection Take map', error);
				d.fields_dict.takes_html.$wrapper.find(`#${map_id}`).html(`
					<div class="text-danger" style="padding: 24px;">
						${__('The Inspection Take map could not be rendered. Reload the form and try again.')}
					</div>
				`);
			}
		});
	});
	d.$wrapper.on('hidden.bs.modal', () => {
		if (rendered_map && rendered_map.map) rendered_map.map.remove();
	});
	d.show();
}

function render_inspection_take_map(frm, dialog, takes, geojson, map_id) {
	const map_element = dialog.fields_dict.takes_html.$wrapper.find(`#${map_id}`)[0];
	if (!map_element) throw new Error('Inspection Take map container is missing');

	const valid_takes = takes.filter((take) => {
		const latitude = Number(take.latitude);
		const longitude = Number(take.longitude);
		return Number.isFinite(latitude)
			&& Number.isFinite(longitude)
			&& latitude >= -90
			&& latitude <= 90
			&& longitude >= -180
			&& longitude <= 180
			&& (latitude !== 0 || longitude !== 0);
	});
	if (!valid_takes.length) {
		$(map_element).html(`
			<div class="text-muted" style="padding: 24px;">
				${__('No valid Inspection Take coordinates are available for this map.')}
			</div>
		`);
		return { map: null, markers: {} };
	}

	const first_point = [flt(valid_takes[0].latitude), flt(valid_takes[0].longitude)];
	const map = L.map(map_element).setView(first_point, 18);
	const map_defaults = (frappe.utils && frappe.utils.map_defaults) || {};
	L.tileLayer(
		map_defaults.tiles || 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
		map_defaults.options || { attribution: 'OpenStreetMap', maxZoom: 19 }
	).addTo(map);
	L.control.scale({ imperial: false }).addTo(map);

	const boundary_features = (geojson.features || []).filter(
		(feature) => feature.properties && feature.properties.type === 'plot_boundary'
	);
	if (boundary_features.length) {
		L.geoJSON(
			{ type: 'FeatureCollection', features: boundary_features },
			{ style: { color: '#2563eb', weight: 2, fillOpacity: 0.08 } }
		).addTo(map);
	}

	const markers = {};
	let previous_take = null;
	valid_takes.forEach((take, index) => {
		const take_number = cint(take.take_number || take.idx);
		const point = [flt(take.latitude), flt(take.longitude)];
		const accuracy_color = take.gps_quality_status === 'Good'
			? '#16a34a'
			: take.gps_quality_status === 'Acceptable' ? '#d97706' : '#dc2626';

		if (previous_take) {
			const segment_color = take.spacing_status === 'Within Standard' ? '#16a34a' : '#dc2626';
			L.polyline(
				[
					[flt(previous_take.latitude), flt(previous_take.longitude)],
					point
				],
				{ color: segment_color, weight: 4, opacity: 0.9 }
			)
				.bindTooltip(
					__('Take {0} to {1}: {2}', [
						cint(previous_take.take_number || previous_take.idx),
						take_number,
						format_take_number(take.distance_from_previous_take_m, 1, 'm')
					])
				)
				.addTo(map);
		}

		if (flt(take.gps_accuracy_meters) > 0) {
			L.circle(point, {
				radius: flt(take.gps_accuracy_meters),
				color: accuracy_color,
				weight: 1,
				fillColor: accuracy_color,
				fillOpacity: 0.08,
				interactive: false
			}).addTo(map);
		}
		if (index < valid_takes.length - 1 && flt(frm.doc.target_take_spacing_m) > 0) {
			L.circle(point, {
				radius: flt(frm.doc.target_take_spacing_m),
				color: '#6b7280',
				weight: 1,
				dashArray: '4 4',
				fillOpacity: 0,
				interactive: false
			}).addTo(map);
		}

		const marker = L.circleMarker(point, {
			radius: 8,
			color: '#111827',
			weight: 2,
			fillColor: cint(take.inside_plot_boundary) ? '#16a34a' : '#dc2626',
			fillOpacity: 1
		})
			.bindTooltip(__('Take {0}', [take_number]), { direction: 'top', offset: [0, -7] })
			.bindPopup(build_take_popup(take, take_number))
			.addTo(map);
		markers[take_number] = marker;
		previous_take = take;
	});

	const marker_group = L.featureGroup(Object.values(markers));
	const fit_map = () => {
		map.invalidateSize(true);
		if (Object.keys(markers).length === 1) {
			map.setView(first_point, 19);
		} else if (marker_group.getBounds().isValid()) {
			map.fitBounds(marker_group.getBounds(), { padding: [40, 40], maxZoom: 19 });
		}
	};
	requestAnimationFrame(() => setTimeout(fit_map, 50));
	return { map, markers };
}

function build_take_popup(take, take_number) {
	if (!take) return escape_take_value(__('Take {0}', [take_number]));
	return `
		<div style="min-width: 180px;">
			<strong>${escape_take_value(__('Take {0}', [take_number]))}</strong><br>
			<span style="font-family: monospace;">${flt(take.latitude).toFixed(8)}, ${flt(take.longitude).toFixed(8)}</span><br>
			<span>${escape_take_value(__('GPS accuracy: {0}', [
				format_take_number(take.gps_accuracy_meters, 1, 'm')
			]))}</span><br>
			<span>${escape_take_value(__('GPS quality: {0}', [take.gps_quality_status || '-']))}</span><br>
			<span>${escape_take_value(__('Spacing: {0} ({1})', [
				format_take_number(take.distance_from_previous_take_m, 1, 'm'),
				take.spacing_status || '-'
			]))}</span><br>
			<span>${escape_take_value(format_take_datetime(take.captured_at))}</span>
		</div>
	`;
}

function format_take_datetime(value) {
	return value ? frappe.datetime.str_to_user(value) : '-';
}

function format_take_number(value, precision, suffix) {
	if (value === null || value === undefined || value === '') return '-';
	return `${format_number(flt(value), null, precision)} ${suffix || ''}`.trim();
}

function escape_take_value(value) {
	return frappe.utils.escape_html(String(value ?? ''));
}

function load_leaflet(callback) {
	if (!document.getElementById('leaflet-css')) {
		let link = document.createElement('link');
		link.id = 'leaflet-css';
		link.rel = 'stylesheet';
		link.href = '/assets/frappe/js/lib/leaflet/leaflet.css';
		document.head.appendChild(link);
	}
	if (typeof L !== 'undefined') {
		callback();
		return;
	}
	frappe.require('/assets/frappe/js/lib/leaflet/leaflet.js', callback);
}
