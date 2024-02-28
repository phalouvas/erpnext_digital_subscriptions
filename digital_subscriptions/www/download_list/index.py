import frappe
from frappe import _

sitemap = 1


def get_context(context):
	user = frappe.session.user

	customer_names = frappe.db.get_all("Portal User", filters={"user": user, "parenttype": "Customer"}, fields=["parent"])
	customer_name = customer_names[0].parent if customer_names else None

	context.paid = frappe.get_all(
			"File Subscription",
			filters={"customer": customer_name, "disabled": 0, "ends_on": ['>', frappe.utils.now()]},
			fields=["name", "item", "item.item_name", "starts_on", "ends_on"]
		)

	context.free = frappe.db.sql(f"""
		SELECT DISTINCT
			TFileVersion.item AS name,
			TItem.item_name AS item_name
		FROM `tabFile Version` AS TFileVersion
			LEFT JOIN `tabItem` AS TItem ON TFileVersion.item = TItem.name
		WHERE TFileVersion.is_free = 1
	""", as_dict=True)

	context.no_cache = 1
	context.show_sidebar = True
