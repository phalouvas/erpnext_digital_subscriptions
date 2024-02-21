import frappe
from frappe.exceptions import PermissionError
from frappe.core.doctype.user.user import create_contact
from erpnext.portal.utils import create_party_contact, party_exists

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
			
        create_customer_or_supplier(user.email)

    frappe.db.commit()

    return ["Migration completed successfully."]

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

	# create customer / supplier if the user has that role
	if portal_settings.default_role and portal_settings.default_role in user_roles:
		doctype = portal_settings.default_role
	else:
		doctype = None

	if not doctype:
		return

	if party_exists(doctype, user):
		party = frappe.get_doc(doctype, {"email_id": user})
		if not frappe.db.exists("Portal User", {"user": user}):
			portal_user = frappe.new_doc("Portal User")
			portal_user.user = user
			party.append("portal_users", portal_user)
			fullname = frappe.utils.get_fullname(user)
			party.customer_name = fullname
			party.save(ignore_permissions=True)
		return

	party = frappe.new_doc(doctype)
	fullname = frappe.utils.get_fullname(user)

	if not doctype == "Customer":
		party.update(
			{
				"supplier_name": fullname,
				"supplier_group": "All Supplier Groups",
				"supplier_type": "Individual",
			}
		)

	party.flags.ignore_mandatory = True
	party.insert(ignore_permissions=True)

	alternate_doctype = "Customer" if doctype == "Supplier" else "Supplier"

	if party_exists(alternate_doctype, user):
		# if user is both customer and supplier, alter fullname to avoid contact name duplication
		fullname += "-" + doctype

	create_party_contact(doctype, fullname, user, party.name)

	return party