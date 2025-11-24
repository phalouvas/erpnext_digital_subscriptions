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
    """
    Link existing Contact (created by Frappe) to Customer/Supplier.
    Waits for Frappe's background job to create the Contact before linking.
    """
    import time
    
    max_retries = 6
    retry_delay = 0.4  # 400ms
    
    for attempt in range(max_retries):
        try:
            # Commit transaction to see changes from other processes
            frappe.db.commit()
            
            # Check if contact exists (created by Frappe's background job)
            contact_name = frappe.db.get_value("Contact", {"email_id": user})
            
            if contact_name:
                # Contact exists, link it to Customer/Supplier
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
                
                # Set as primary contact on Customer
                if doctype == "Customer":
                    party = frappe.get_doc("Customer", party_name)
                    if not party.customer_primary_contact:
                        party.db_set("customer_primary_contact", contact.name)
                
                return contact
            else:
                # Contact doesn't exist yet
                if attempt < max_retries - 1:
                    # Wait for Frappe's background job to create it
                    time.sleep(retry_delay)
                    continue
                else:
                    # After all retries, create it ourselves as fallback
                    frappe.log_error(
                        f"Contact not found for {user} after {max_retries} attempts. Creating manually.",
                        "Contact Creation Fallback"
                    )
                    contact = frappe.new_doc("Contact")
                    contact.update({"first_name": fullname, "email_id": user})
                    contact.append("links", dict(link_doctype=doctype, link_name=party_name))
                    contact.append("email_ids", dict(email_id=user, is_primary=True))
                    contact.flags.ignore_mandatory = True
                    contact.insert(ignore_permissions=True)
                    
                    # Set as primary contact on Customer
                    if doctype == "Customer":
                        party = frappe.get_doc("Customer", party_name)
                        if not party.customer_primary_contact:
                            party.db_set("customer_primary_contact", contact.name)
                    
                    return contact
                    
        except frappe.QueryDeadlockError:
            # Deadlock occurred, rollback and retry
            frappe.db.rollback()
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            else:
                frappe.log_error(
                    f"Deadlock creating/linking contact for {user} after {max_retries} attempts",
                    "Contact Deadlock Error"
                )
                return None
                
        except (frappe.DuplicateEntryError, frappe.TimestampMismatchError):
            # Contact was created/modified by another process
            frappe.db.rollback()
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                frappe.log_error(
                    f"Conflict creating/linking contact for {user}",
                    "Contact Creation Conflict"
                )
                return None
                
        except Exception as e:
            # Unexpected error, log and return None for graceful degradation
            frappe.log_error(
                f"Error in create_party_contact for {user}: {str(e)}\n{frappe.get_traceback()}",
                "Contact Creation Error"
            )
            return None
    
    return None