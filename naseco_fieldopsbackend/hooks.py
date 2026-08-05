app_name = "naseco_fieldopsbackend"
app_title = "Naseco FieldOpsBackend"
app_publisher = "Naseco"
app_description = "Backend for Naseco FieldOps Mobile App"
app_email = "admin@naseco.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "naseco_fieldopsbackend",
# 		"logo": "/assets/naseco_fieldopsbackend/logo.png",
# 		"title": "Naseco FieldOpsBackend",
# 		"route": "/naseco_fieldopsbackend",
# 		"has_permission": "naseco_fieldopsbackend.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/naseco_fieldopsbackend/css/naseco_fieldopsbackend.css"
# app_include_js = "/assets/naseco_fieldopsbackend/js/naseco_fieldopsbackend.js"

# include js, css files in header of web template
# web_include_css = "/assets/naseco_fieldopsbackend/css/naseco_fieldopsbackend.css"
# web_include_js = "/assets/naseco_fieldopsbackend/js/naseco_fieldopsbackend.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "naseco_fieldopsbackend/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "naseco_fieldopsbackend/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "naseco_fieldopsbackend.utils.jinja_methods",
# 	"filters": "naseco_fieldopsbackend.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "naseco_fieldopsbackend.install.before_install"
# after_install = "naseco_fieldopsbackend.setup_fieldops.create_cust_fields"

# Uninstallation
# ------------

# before_uninstall = "naseco_fieldopsbackend.uninstall.before_uninstall"
# after_uninstall = "naseco_fieldopsbackend.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "naseco_fieldopsbackend.utils.before_app_install"
# after_app_install = "naseco_fieldopsbackend.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "naseco_fieldopsbackend.utils.before_app_uninstall"
# after_app_uninstall = "naseco_fieldopsbackend.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "naseco_fieldopsbackend.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

permission_query_conditions = {
	"Outgrower": "naseco_fieldopsbackend.permissions.outgrower_query",
	"Farm Plot": "naseco_fieldopsbackend.permissions.farm_plot_query",
	"Crop Cycle": "naseco_fieldopsbackend.permissions.crop_cycle_query",
	"Stage Activity": "naseco_fieldopsbackend.permissions.stage_activity_query",
	"Agronomy Report": "naseco_fieldopsbackend.permissions.agronomy_report_query",
	"Inspection": "naseco_fieldopsbackend.permissions.inspection_query",
	"Field Corrective Action": "naseco_fieldopsbackend.permissions.corrective_action_query",
	"Crop Production Lot": "naseco_fieldopsbackend.permissions.production_lot_query",
	"Seed Harvest Quality Assessment": "naseco_fieldopsbackend.permissions.harvest_quality_query",
}
has_permission = {
	"Outgrower": "naseco_fieldopsbackend.permissions.has_permission",
	"Farm Plot": "naseco_fieldopsbackend.permissions.has_permission",
	"Crop Cycle": "naseco_fieldopsbackend.permissions.has_permission",
	"Stage Activity": "naseco_fieldopsbackend.permissions.has_permission",
	"Agronomy Report": "naseco_fieldopsbackend.permissions.has_permission",
	"Inspection": "naseco_fieldopsbackend.permissions.has_permission",
	"Field Corrective Action": "naseco_fieldopsbackend.permissions.has_permission",
	"Crop Production Lot": "naseco_fieldopsbackend.permissions.has_permission",
	"Seed Harvest Quality Assessment": "naseco_fieldopsbackend.permissions.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Stock Entry": {
		"before_validate": "naseco_fieldopsbackend.fieldops_finance.populate_stock_entry_context",
		"before_submit": "naseco_fieldopsbackend.fieldops_finance.populate_stock_entry_context",
		"on_submit": "naseco_fieldopsbackend.fieldops_finance.sync_input_request_from_stock",
		"on_cancel": "naseco_fieldopsbackend.fieldops_finance.sync_input_request_from_stock",
	},
	"Payment Entry": {
		"on_submit": "naseco_fieldopsbackend.fieldops_finance.sync_advance_request_from_payment",
		"on_cancel": "naseco_fieldopsbackend.fieldops_finance.sync_advance_request_from_payment",
	},
	"Purchase Receipt": {
		"before_validate": "naseco_fieldopsbackend.fieldops_finance.populate_purchase_receipt_context",
	},
	"Purchase Invoice": {
		"on_submit": "naseco_fieldopsbackend.fieldops_finance.sync_settlement_from_invoice",
		"on_cancel": "naseco_fieldopsbackend.fieldops_finance.sync_settlement_from_invoice",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
# 	"all": [
# 		"naseco_fieldopsbackend.tasks.all"
# 	],
	"daily": [
		"naseco_fieldopsbackend.lifecycle_tasks.update_active_crop_cycle_stages",
		"naseco_fieldopsbackend.naseco_fieldopsbackend.doctype.season.season.update_season_statuses",
	],
# 	"hourly": [
# 		"naseco_fieldopsbackend.tasks.hourly"
# 	],
# 	"weekly": [
# 		"naseco_fieldopsbackend.tasks.weekly"
# 	],
# 	"monthly": [
# 		"naseco_fieldopsbackend.tasks.monthly"
# 	],
}

# Testing
# -------

# before_tests = "naseco_fieldopsbackend.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "naseco_fieldopsbackend.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "naseco_fieldopsbackend.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["naseco_fieldopsbackend.utils.before_request"]
# after_request = ["naseco_fieldopsbackend.utils.after_request"]

# Job Events
# ----------
# before_job = ["naseco_fieldopsbackend.utils.before_job"]
# after_job = ["naseco_fieldopsbackend.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"naseco_fieldopsbackend.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

fixtures = [
    {"dt": "Role", "filters": {"name": ["in", [
        "Outgrower Supervisor", "Outgrower Manager", "Quality Inspector",
        "FieldOps Finance Approver", "FieldOps Stores User", "FieldOps Operations Approver"
    ]]}},
    {"dt": "Outgrower"},
    {"dt": "Farm Plot"},
    {"dt": "Custom Field", "filters": {"module": "NASECO ERP"}},
    {'dt': "Client Script", 'filters': {"module": "NASECO ERP"}}
]
# Fixtures
# ------------------
