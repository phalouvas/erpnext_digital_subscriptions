import frappe
import erpnext.portal.utils
import time

from erpnext.selling.doctype.customer.customer import Customer as ERPNextCustomer

logger = frappe.logger("digital_subscriptions")

_original_create_primary_contact = ERPNextCustomer.create_primary_contact


def _acquire_lock(lock_key, timeout=30):
    """
    Acquire distributed lock using frappe.cache().
    Returns True if lock acquired, False otherwise.
    """
    try:
        # nx=True means set only if not exists, ex=timeout sets expiry in seconds
        return frappe.cache().set(lock_key, "1", ex=timeout, nx=True)
    except Exception:
        # If cache doesn't support nx parameter, fall back to simpler locking
        try:
            if frappe.cache().get(lock_key):
                return False
            frappe.cache().set(lock_key, "1", ex=timeout)
            return True
        except Exception:
            # Last resort: log and proceed without locking
            frappe.log_error(
                f"Cache locking failed for key {lock_key}",
                "Digital Subscriptions Lock Error"
            )
            return True  # Proceed anyway to avoid blocking


def _release_lock(lock_key):
    """Release distributed lock."""
    try:
        frappe.cache().delete(lock_key)
    except Exception:
        pass


def _resolve_user(user=None):
    if user:
        return user

    session = getattr(frappe, "session", None)
    session_user = getattr(session, "user", None)
    if session_user and session_user != "Guest":
        return session_user

    return None


def _get_existing_party_for_user(doctype, user):
    if not user:
        return None

    party_name = frappe.db.get_value(
        "Portal User",
        {"parenttype": doctype, "user": user},
        "parent",
    )
    if party_name and frappe.db.exists(doctype, party_name):
        return frappe.get_doc(doctype, party_name)

    contact_name = frappe.db.get_value("Contact", {"email_id": user})
    if not contact_name:
        return None

    try:
        contact = frappe.get_doc("Contact", contact_name)
    except frappe.DoesNotExistError:
        return None

    for link in contact.links:
        if link.link_doctype == doctype and frappe.db.exists(doctype, link.link_name):
            return frappe.get_doc(doctype, link.link_name)

    return None


def create_customer_or_supplier(user=None):
    """Custom implementation that overrides the original function."""
    user = _resolve_user(user)
    if not user:
        return

    if frappe.db.get_value("User", user, "user_type") != "Website User":
        return

    user_roles = frappe.get_roles(user)
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

    existing_party = _get_existing_party_for_user(doctype, user)
    if existing_party:
        return existing_party

    # Acquire distributed lock for this user and doctype to prevent concurrent creation
    lock_key = f"party_creation_lock:{user}:{doctype}"
    if not _acquire_lock(lock_key):
        # Wait briefly and check if party was created by another process
        time.sleep(0.5)
        if erpnext.portal.utils.party_exists(doctype, user):
            # Party exists now, return None (original function returns None when party exists)
            return
        # Try one more time to acquire lock
        time.sleep(0.5)
        if not _acquire_lock(lock_key):
            # Could not acquire lock, log and return to avoid blocking
            frappe.log_error(
                f"Could not acquire lock for {doctype} creation for user {user}",
                "Party Creation Lock Error"
            )
            return

    logger.info(f"Creating {doctype} for user {user}")
    try:
        # Double-check after acquiring lock
        existing_party = _get_existing_party_for_user(doctype, user)
        if existing_party:
            logger.info(f"{doctype} already exists for user {user}: {existing_party.name}")
            return existing_party

        # Get and validate fullname
        fullname = frappe.utils.get_fullname(user).strip()
        if not fullname:
            # Fallback to email username if name is empty
            fullname = user.split('@')[0]
            logger.warning(f"Empty name for user {user}, using '{fullname}'")
        
        # Check for alternate party BEFORE creating this one
        alternate_doctype = "Customer" if doctype == "Supplier" else "Supplier"
        if _get_existing_party_for_user(alternate_doctype, user):
            # User has both roles, add suffix to avoid confusion
            fullname += "-" + doctype
        
        # Create party with final name (including suffix if needed)
        party = frappe.new_doc(doctype)
        if doctype == "Customer":
            party.update({"customer_name": fullname})
        else:
            party.update({
                "supplier_name": fullname,
                "supplier_group": "All Supplier Groups",
                "supplier_type": "Individual",
            })

        party.append("portal_users", {"user": user})
        party.flags.ignore_mandatory = True
        party.flags.ignore_links = True
        party.insert(ignore_permissions=True)
        logger.info(f"{doctype} created: {party.name} ('{fullname}') for user {user}")

        # Link contact (passive - waits for Frappe's background job)
        create_party_contact(doctype, fullname, user, party.name)

        return party
    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        existing_party = _get_existing_party_for_user(doctype, user)
        if existing_party:
            return existing_party
        raise
    finally:
        _release_lock(lock_key)

def create_party_contact(doctype, fullname, user, party_name):
    """
    PASSIVE: Link existing Contact (created by Frappe) to Customer/Supplier.
    Waits for Frappe's background job to create the Contact before linking.
    Does not create Contacts - relies on Frappe's background job to avoid race conditions.
    """
    max_retries = 8
    base_delay = 0.2
    
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
                    contact.flags.ignore_links = True
                    contact.flags.ignore_mandatory = True
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
                    # Wait for Frappe's background job with bounded exponential backoff
                    delay = min(base_delay * (2 ** attempt), 1.6)
                    time.sleep(delay)
                    continue
                else:
                    # Contact not found after all retries
                    # Log this for monitoring, but don't create manually to avoid race conditions
                    frappe.log_error(
                        f"Contact not found for {user} after {max_retries} attempts. "
                        f"Frappe's background job should create it. "
                        f"Party: {doctype} '{party_name}' created without linked Contact.",
                        "Contact Not Found After Retries"
                    )
                    return None
                    
        except frappe.QueryDeadlockError:
            # Deadlock occurred, rollback and retry
            frappe.db.rollback()
            if attempt < max_retries - 1:
                time.sleep(min(base_delay * (2 ** attempt), 1.6))
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
                time.sleep(base_delay)
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