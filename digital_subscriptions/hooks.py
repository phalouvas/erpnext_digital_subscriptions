from . import __version__ as app_version

app_name = "digital_subscriptions"
app_title = "Digital Subscriptions"
app_publisher = "KAINOTOMO PH LTD"
app_description = "Sell subscriptions for file download"
app_email = "info@kainotomo.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/digital_subscriptions/css/digital_subscriptions.css"
# app_include_js = "/assets/digital_subscriptions/js/digital_subscriptions.js"

# include js, css files in header of web template
web_include_css = "digital_subscriptions.bundle.css"
# web_include_js = "/assets/digital_subscriptions/js/digital_subscriptions.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "digital_subscriptions/public/scss/website"

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

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "digital_subscriptions.utils.jinja_methods",
#	"filters": "digital_subscriptions.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "digital_subscriptions.install.before_install"
# after_install = "digital_subscriptions.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "digital_subscriptions.uninstall.before_uninstall"
# after_uninstall = "digital_subscriptions.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "digital_subscriptions.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }
has_website_permission = {
	"Item Group": "digital_subscriptions.digital_subscriptions.hooks.item_group.has_website_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Payment Entry": {
        "on_submit": "digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.create_file_subscription"
    },
    "Customer": {
        "validate": "digital_subscriptions.digital_subscriptions.web_form.vies.vies.validate_vies"
    }
}
on_session_creation = "digital_subscriptions.digital_subscriptions.web_form.vies.vies.create_customer_or_supplier"

# doc_events = {
#	"*": {
#		"on_update": "method",
#		"on_cancel": "method",
#		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
#	"all": [
#		"digital_subscriptions.tasks.all"
#	],
#	"daily": [
#		"digital_subscriptions.tasks.daily"
#	],
#	"hourly": [
#		"digital_subscriptions.tasks.hourly"
#	],
#	"weekly": [
#		"digital_subscriptions.tasks.weekly"
#	],
#	"monthly": [
#		"digital_subscriptions.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "digital_subscriptions.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "digital_subscriptions.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "digital_subscriptions.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["digital_subscriptions.utils.before_request"]
# after_request = ["digital_subscriptions.utils.after_request"]

# Job Events
# ----------
# before_job = ["digital_subscriptions.utils.before_job"]
# after_job = ["digital_subscriptions.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"digital_subscriptions.auth.validate"
# ]
