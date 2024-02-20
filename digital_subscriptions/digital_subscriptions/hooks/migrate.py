import frappe
from frappe.exceptions import PermissionError
from frappe.core.doctype.user.user import create_contact
import re

@frappe.whitelist(allow_guest=False)
def migrate():
    if not frappe.session.user == "Administrator":
        raise PermissionError("Only the Administrator can perform the migration.")
    
    # Get all users from table `rc11v_users`
    users = frappe.db.sql("SELECT * FROM `rc11v_users` LIMIT 1", as_dict=True)
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
    
    # commit
    frappe.db.commit()


    # Get all subscriptions from table `rc11v_spdigitalsubs_transactions`
    subscriptions = frappe.db.sql("SELECT * FROM `rc11v_spdigitalsubs_transactions` LIMIT 1", as_dict=True)

    return [users, subscriptions]