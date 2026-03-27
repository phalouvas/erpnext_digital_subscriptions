__version__ = '16.1.0'

import frappe
import frappe.core.doctype.user.user as frappe_user
import erpnext.portal.utils as erpnext_portal_utils

from erpnext.selling.doctype.customer.customer import Customer as ERPNextCustomer

from digital_subscriptions.overrides import _create_contact_safely
from digital_subscriptions.overrides import _create_safe_patch
from digital_subscriptions.overrides import _get_contact_by_email
from digital_subscriptions.overrides import _increment_contact_metric
from digital_subscriptions.overrides import _link_contact_to_party_safely
from digital_subscriptions.overrides import _update_contact_safely
from digital_subscriptions.overrides import _validate_function_signature
from digital_subscriptions.overrides import _with_contact_lock
from digital_subscriptions.overrides import create_customer_or_supplier
from digital_subscriptions.overrides import create_party_contact
from digital_subscriptions.overrides import create_primary_contact

logger = frappe.logger("digital_subscriptions")

_ORIGINAL_FRAPPE_CREATE_CONTACT = getattr(frappe_user, "create_contact", None)
_ORIGINAL_PORTAL_CREATE_CUSTOMER_OR_SUPPLIER = getattr(
    erpnext_portal_utils, "create_customer_or_supplier", None
)
_ORIGINAL_PORTAL_CREATE_PARTY_CONTACT = getattr(erpnext_portal_utils, "create_party_contact", None)


def create_contact(user, ignore_links=False, ignore_mandatory=False):
    user_doc = user if getattr(user, "doctype", None) == "User" else frappe.get_doc("User", user)

    if user_doc.name in ["Administrator", "Guest"]:
        return None

    email = getattr(user_doc, "email", None) or user_doc.name
    lock_key = f"{email}:background_job"

    def _coordinated_contact_operation():
        contact_name = _get_contact_by_email(email)
        if contact_name:
            return _update_contact_safely(
                contact_name,
                user_doc,
                ignore_links=ignore_links,
                ignore_mandatory=ignore_mandatory,
            )

        return _create_contact_safely(
            user_doc,
            ignore_links=ignore_links,
            ignore_mandatory=ignore_mandatory,
        )

    try:
        contact_name = _with_contact_lock(
            lock_key,
            _coordinated_contact_operation,
            fallback=lambda: _get_contact_by_email(email),
        )
        if contact_name:
            _link_contact_to_party_safely(contact_name, "User", user_doc.name)
        _increment_contact_metric("coordinated")
        return None
    except frappe.QueryDeadlockError:
        frappe.db.rollback()
        _increment_contact_metric("deadlock")
        logger.warning("Retrying create_contact background job for %s after deadlock", email)
        raise frappe.RetryBackgroundJobError
    except frappe.TimestampMismatchError:
        frappe.db.rollback()
        _increment_contact_metric("timestamp_conflict")
        logger.warning("Retrying create_contact background job for %s after timestamp conflict", email)
        raise frappe.RetryBackgroundJobError
    except Exception:
        logger.error(
            "Unified create_contact failed for %s.\n%s",
            email,
            frappe.get_traceback(),
        )
        raise


def _apply_patch(module, func_name, patched_func, expected_args, original_func=None):
    if not _validate_function_signature(module, func_name, expected_args):
        logger.warning(
            "Skipping patch for %s.%s due to unexpected signature",
            getattr(module, "__name__", repr(module)),
            func_name,
        )
        return False

    safe_patch = _create_safe_patch(original_func or getattr(module, func_name, None), patched_func)
    setattr(module, func_name, safe_patch)
    logger.info("Applied patch for %s.%s", getattr(module, "__name__", repr(module)), func_name)
    return True


_apply_patch(
    frappe_user,
    "create_contact",
    create_contact,
    ("user", "ignore_links", "ignore_mandatory"),
    _ORIGINAL_FRAPPE_CREATE_CONTACT,
)

_apply_patch(
    erpnext_portal_utils,
    "create_customer_or_supplier",
    create_customer_or_supplier,
    (),
    _ORIGINAL_PORTAL_CREATE_CUSTOMER_OR_SUPPLIER,
)

_apply_patch(
    erpnext_portal_utils,
    "create_party_contact",
    create_party_contact,
    ("doctype", "fullname", "user", "party_name"),
    _ORIGINAL_PORTAL_CREATE_PARTY_CONTACT,
)

ERPNextCustomer.create_primary_contact = create_primary_contact
logger.info("Applied patch for ERPNextCustomer.create_primary_contact")

try:
    import digital_subscriptions.digital_subscriptions.hooks.migrate as migrate_hooks

    migrate_hooks.create_contact = frappe_user.create_contact
except Exception:
    logger.debug("Migrate hook import unavailable during patch bootstrap")

try:
    import webshop.webshop.utils.portal as webshop_portal

    def patched_update_debtors_account():
        return create_customer_or_supplier()

    webshop_portal.update_debtors_account = _create_safe_patch(
        getattr(webshop_portal, "update_debtors_account", None),
        patched_update_debtors_account,
    )
    logger.info(
        "Monkey-patched webshop.update_debtors_account to use digital_subscriptions"
    )
except ImportError:
    pass
