import frappe
from frappe import _

sitemap = 1


def get_context(context):
	user = frappe.get_doc("User", frappe.session.user)

	subscriptions = frappe.get_all(
			"File Subscription",
			filters={"customer": user.full_name, "disabled": 0, "ends_on": ['>', frappe.utils.now()]},
			fields=["name", "item", "item.item_name", "starts_on", "ends_on"]
		)

	context.docs = subscriptions
