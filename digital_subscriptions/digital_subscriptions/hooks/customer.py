import frappe

def before_insert(doc, method):
    if doc.email_id:
        user = frappe.get_all("User", filters={"email": doc.email_id}, fields=["name"])
        if not user:
            user = frappe.get_doc({
                "doctype": "User",
                "email": doc.email_id,
                "first_name": doc.customer_name,
                "enabled": 1,
                "user_type": "Website User",
                "send_welcome_email": 0
            })
            user.append("roles", {"role": "Customer"})
            user.insert(ignore_permissions=True)
            frappe.db.commit()
            doc.append("portal_users", {"user": user.name})
        else:
            doc.append("portal_users", {"user": user[0].name})
    pass