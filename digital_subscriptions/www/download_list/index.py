import frappe
from frappe import _

sitemap = 1


def get_context(context):
	user = frappe.session.user

	contact_name = frappe.db.get_value("Contact", {"email_id": user})
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for link in contact.links:
			if link.link_doctype == "Customer":
				customer = frappe.get_doc("Customer", link.link_name)

	if not customer:
		customer_name = ""
	else:
		customer_name = customer.name

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

	context.no_cache = 0
	context.show_sidebar = True
