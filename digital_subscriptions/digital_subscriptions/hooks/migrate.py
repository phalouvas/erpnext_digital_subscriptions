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
		create_customer(user)

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
		link_customer(user.email)

	frappe.db.commit()
	return ["Migration completed successfully."]
	
def create_customer(user):
	doctype = "Customer"

	if party_exists(doctype, user.email):		
		return

	party = frappe.new_doc(doctype)
	fullname = user.name
	party.customer_name = fullname

	party.flags.ignore_mandatory = True
	party.insert(ignore_permissions=True)

	create_party_contact(doctype, fullname, user, party.name)
	frappe.db.commit()

	return party

def link_customer(user):
	if frappe.db.get_value("User", user, "user_type") != "Website User":
		return

	doctype = "Customer"

	if party_exists(doctype, user):
		party = frappe.get_doc(doctype, {"email_id": user})
		if not frappe.db.exists("Portal User", {"user": user}):
			portal_user = frappe.new_doc("Portal User")
			portal_user.user = user
			party.append("portal_users", portal_user)
			fullname = frappe.utils.get_fullname(user)
			party.customer_name = fullname
			party.save(ignore_permissions=True)
