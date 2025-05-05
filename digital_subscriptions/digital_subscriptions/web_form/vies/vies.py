import requests
import frappe
from xml.etree import ElementTree as ET
from frappe.model.rename_doc import update_document_title, rename_doc

def get_context(context):
	pass

def create_customer_or_supplier():
	"""Based on the default Role (Customer, Supplier), create a Customer / Supplier.
	Called on_session_creation hook.
	"""
	user = frappe.session.user

	if frappe.db.get_value("User", user, "user_type") != "Website User":
		return

	user_roles = frappe.get_roles()
	portal_settings = frappe.get_single("Portal Settings")
	default_role = portal_settings.default_role

	if default_role not in ["Customer"]:
		return

	# get customer
	if portal_settings.default_role and portal_settings.default_role in user_roles:
		doctype = portal_settings.default_role
	else:
		doctype = None

	if not doctype:
		return

	contact_name = frappe.db.get_value("Contact", {"email_id": user})
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for link in contact.links:
			if link.link_doctype == doctype:
				party = frappe.get_doc(doctype, link.link_name)

	if not party:
		return

	if not frappe.db.exists("Portal User", {"user": user}):
		fullname = frappe.utils.get_fullname(user)
		if party.name != fullname:
			new_name = rename_doc(
				doctype = doctype, 
				old = party.name, 
				new = fullname, 
				force=False, 
				merge=False, 
				ignore_permissions = True, 
				ignore_if_exists = False, 
				show_alert = False,
				rebuild_search = True,
				doc = None,
				validate= True)
			party = frappe.get_doc(doctype, new_name)
		portal_user = frappe.new_doc("Portal User")
		portal_user.user = user
		party.append("portal_users", portal_user)
		party.customer_name = fullname
		if not party.customer_primary_contact:
			party.customer_primary_contact = contact_name
		party.save(ignore_permissions=True)

	return party
