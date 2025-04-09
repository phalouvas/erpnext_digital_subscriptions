import frappe

def after_insert(doc, method):
    """Create a new contact if it does not exist"""
    # 1. If the contact.name is not there return
    contact_name = doc.name
    if not contact_name:
        return

    # 2. Get the connected user. If not user return
    email_id = frappe.get_value("Contact", contact_name, "email_id")
    if not email_id:
        return

    # check if user is already in the system - include user_type in the same query
    user = frappe.get_all("User", 
                         filters={"email": email_id}, 
                         fields=["name", "user_type"])
    if not user:
        return
    
    user_name = user[0].name
    
    # Check if the user is a Website User
    if user[0].user_type != "Website User":
        return
    
    # Check if user has a role defined in Portal Settings
    portal_role = frappe.db.get_single_value("Portal Settings", "default_role")
    if portal_role:
        user_roles = frappe.get_roles(user_name)
        if portal_role not in user_roles:
            return
    
    # 3. Get the customer related with the user using a direct query
    # This is much more efficient than retrieving all customers and looping
    portal_user_records = frappe.get_all(
        "Portal User",
        filters={"user": user_name, "parenttype": "Customer"},
        fields=["parent"],
        limit=1
    )
    
    # 4. If the customer exists return
    if portal_user_records:
        return  # User is already linked to a customer, exit
    
    # 5. If the customer does not exist, create the customer and relate the contact with the customer
    new_customer = frappe.new_doc("Customer")
    new_customer.customer_name = doc.first_name + (f" {doc.last_name}" if doc.last_name else "")
    new_customer.customer_type = "Company"
    
    # Add the user to portal_users
    new_customer.append("portal_users", {
        "user": user_name
    })
    
    # First save the customer without email_id to avoid creating another contact
    new_customer.insert(ignore_permissions=True)
    
    # Now update the customer with email_id and set customer_primary_contact
    new_customer.customer_primary_contact = contact_name
    new_customer.save(ignore_permissions=True)
    
    # Link the contact to the customer
    doc.append("links", {
        "link_doctype": "Customer",
        "link_name": new_customer.name
    })
    doc.save(ignore_permissions=True)