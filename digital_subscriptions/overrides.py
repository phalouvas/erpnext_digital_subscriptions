import frappe
import erpnext.portal.utils

from erpnext.selling.doctype.customer.customer import Customer as ERPNextCustomer

_original_create_primary_contact = ERPNextCustomer.create_primary_contact

def create_customer_or_supplier():
    """Custom implementation that overrides the original function."""
    user = frappe.session.user

    if frappe.db.get_value("User", user, "user_type") != "Website User":
        return

    user_roles = frappe.get_roles()
    portal_settings = frappe.get_single("Portal Settings")
    default_role = portal_settings.default_role

    if default_role not in ["Customer", "Supplier"]:
        return

    # create customer / supplier if the user has that role
    if portal_settings.default_role and portal_settings.default_role in user_roles:
        doctype = portal_settings.default_role
    else:
        doctype = None

    if not doctype:
        return

    if erpnext.portal.utils.party_exists(doctype, user):
        return

    party = frappe.new_doc(doctype)
    fullname = frappe.utils.get_fullname(user)

    if doctype == "Customer":
        party.update(
            {
                "customer_name": fullname,
            }
        )
    else:
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

    if erpnext.portal.utils.party_exists(alternate_doctype, user):
        # if user is both customer and supplier, alter fullname to avoid contact name duplication
        fullname += "-" + doctype

    create_party_contact(doctype, fullname, user, party.name)

    return party

def create_party_contact(doctype, fullname, user, party_name):
    """
    Link existing Contact (created by Frappe) to Customer/Supplier.
    Waits for Frappe's background job to create the Contact before linking.
    Does not create Contacts - relies on Frappe's background job to avoid race conditions.
    """
    import time
    
    max_retries = 10  # Increased from 6 to allow more time for background job
    retry_delay = 0.5  # 500ms - slightly longer delay
    
    for attempt in range(max_retries):
        try:
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
                    # Contact not found after all retries
                    # Log this for monitoring, but don't create manually to avoid race conditions
                    frappe.log_error(
                        f"Contact not found for {user} after {max_retries} attempts ({max_retries * retry_delay}s). "
                        f"Frappe's background job should create it. "
                        f"Party: {doctype} '{party_name}' created without linked Contact.",
                        "Contact Not Found After Retries"
                    )
                    return None
                    
        except frappe.QueryDeadlockError:
            # Deadlock occurred, rollback and retry
            frappe.db.rollback()
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            else:
                frappe.log_error(
                    f"Deadlock linking contact for {user} after {max_retries} attempts. "
                    f"Party: {doctype} '{party_name}'",
                    "Contact Link Deadlock Error"
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
                    f"Conflict linking contact for {user}. "
                    f"Party: {doctype} '{party_name}'",
                    "Contact Link Conflict"
                )
                return None
                
        except Exception as e:
            # Unexpected error, log and return None for graceful degradation
            frappe.log_error(
                f"Error in create_party_contact for {user}: {str(e)}\n{frappe.get_traceback()}",
                "Contact Link Error"
            )
            return None
    
    return None


def create_primary_contact(self):
    # TODO(phalouvas): Remove once Webshop fixes login-time Contact permission error.
    # See https://github.com/frappe/webshop/issues/350
    if not self.customer_primary_contact and not self.lead_name:
        return _original_create_primary_contact(self)

    if not self.customer_primary_contact:
        return

    user_type = None
    if getattr(frappe, "session", None) and frappe.session.user:
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type")

    if user_type == "Website User":
        # Avoid permission error during portal login/session creation.
        frappe.db.set_value(
            "Contact",
            self.customer_primary_contact,
            "is_primary_contact",
            1,
            update_modified=False,
        )
        return

    frappe.set_value("Contact", self.customer_primary_contact, "is_primary_contact", 1)