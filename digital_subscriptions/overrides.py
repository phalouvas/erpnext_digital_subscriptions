import frappe
import erpnext.portal.utils

# Store the original function before we override it
original_create_customer_or_supplier = erpnext.portal.utils.create_customer_or_supplier

def create_customer_or_supplier():
    """Custom implementation that overrides the original function."""
    
    # Call the original function implementation directly (not through the module)
    party = original_create_customer_or_supplier()
    
    if party and party.doctype == "Customer":
        user = frappe.session.user
        fullname = frappe.utils.get_fullname(user)
        party.customer_name = fullname
        frappe.db.set_value("Customer", party.name, "customer_name", fullname)
    
    return party

def create_party_contact(doctype, fullname, user, party_name):
    # First check if there's an existing contact with this email
    contact_name = frappe.db.get_value("Contact", {"email_id": user})
    
    if contact_name:
        # If contact exists, get the contact doc
        contact = frappe.get_doc("Contact", contact_name)
        
        # Check if this doctype link already exists
        link_exists = False
        for link in contact.links:
            if link.link_doctype == doctype and link.link_name == party_name:
                link_exists = True
                break
        
        # Add the link if it doesn't exist
        if not link_exists:
            contact.append("links", dict(link_doctype=doctype, link_name=party_name))
            contact.save(ignore_permissions=True)
        
        return contact
    else:
        # Create new contact if none exists
        contact = frappe.new_doc("Contact")
        contact.update({"first_name": fullname, "email_id": user})
        contact.append("links", dict(link_doctype=doctype, link_name=party_name))
        contact.append("email_ids", dict(email_id=user, is_primary=True))
        contact.flags.ignore_mandatory = True
        contact.insert(ignore_permissions=True)
        return contact