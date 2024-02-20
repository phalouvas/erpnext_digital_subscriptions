import frappe
from frappe.exceptions import PermissionError
from frappe.core.doctype.user.user import create_contact
import re

@frappe.whitelist(allow_guest=False)
def migrate():
    if not frappe.session.user == "Administrator":
        raise PermissionError("Only the Administrator can perform the migration.")
    
    # Get all users from table `rc11v_users`
    users = frappe.db.sql("SELECT * FROM `rc11v_users` LIMIT 2", as_dict=True)
    # For each user in `rc11v_users`, create a new user in `tabUser`
    for user in users:
        # Check if the user already exists in `tabUser`
        user_exists = frappe.get_all("User", filters={"email": user.email}, fields=["name"])
        if not user_exists:
            user_doc = frappe.get_doc({
                "doctype": "User",
                "email": user.email,
                "first_name": user.name,
                "username": user.username,
                "enabled": 1,
                "send_welcome_email": 0,
                "roles": [
                    {
                        "role": "Customer"
                    }
                ]
            }).insert()        
            create_contact(user_doc, ignore_links=True, ignore_mandatory=True)
            frappe.db.commit()
			
        create_customer_or_supplier(user.email)
    


    # Get all subscriptions from table `rc11v_spdigitalsubs_transactions`
    subscriptions = frappe.db.sql("SELECT * FROM `rc11v_spdigitalsubs_transactions` LIMIT 1", as_dict=True)

    return [users, subscriptions]

def create_customer_or_supplier(user):
	"""Based on the default Role (Customer, Supplier), create a Customer / Supplier.
	Called on_session_creation hook.
	"""
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
		portal_user = frappe.new_doc("Portal User")
		portal_user.user = user
		party.append("portal_users", portal_user)
		fullname = frappe.utils.get_fullname(user)
		party.customer_name = fullname
		party.save(ignore_permissions=True)

	return party