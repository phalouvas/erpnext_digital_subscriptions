import functools
import inspect
import time

import frappe

from erpnext.selling.doctype.customer.customer import Customer as ERPNextCustomer

logger = frappe.logger("digital_subscriptions")

CONTACT_LOCK_TIMEOUT = 30
CONTACT_LOCK_WAIT_TIMEOUT = 5
CONTACT_CACHE_TTL = 300
CONTACT_METRIC_TTL = 24 * 60 * 60

_original_create_primary_contact = ERPNextCustomer.create_primary_contact


def _cache_get(key):
    cache_factory = getattr(frappe, "cache", None)
    if not callable(cache_factory):
        return None

    try:
        cache = cache_factory()
        if not cache:
            return None
        value = cache.get(key)
    except Exception:
        return None

    if isinstance(value, bytes):
        return value.decode()

    return value


def _cache_set(key, value, expires=None, only_if_missing=False):
    cache_factory = getattr(frappe, "cache", None)
    if not callable(cache_factory):
        return False

    try:
        cache = cache_factory()
    except Exception:
        return False

    if not cache:
        return False

    kwargs = {}
    if expires is not None:
        kwargs["ex"] = expires
    if only_if_missing:
        kwargs["nx"] = True

    try:
        return cache.set(key, value, **kwargs)
    except TypeError:
        if only_if_missing and _cache_get(key):
            return False

        try:
            if expires is not None:
                return cache.set(key, value, ex=expires)
            return cache.set(key, value)
        except Exception:
            return False
    except Exception:
        return False


def _cache_delete(key):
    cache_factory = getattr(frappe, "cache", None)
    if not callable(cache_factory):
        return

    try:
        cache = cache_factory()
        if not cache:
            return
        cache.delete(key)
    except Exception:
        pass


def _increment_contact_metric(metric_name):
    key = f"digital_subscriptions:contact_metric:{metric_name}"
    current_value = _cache_get(key)

    try:
        current_value = int(current_value or 0)
    except (TypeError, ValueError):
        current_value = 0

    _cache_set(key, str(current_value + 1), expires=CONTACT_METRIC_TTL)


def _get_contact_metric(metric_name):
    try:
        return int(_cache_get(f"digital_subscriptions:contact_metric:{metric_name}") or 0)
    except (TypeError, ValueError):
        return 0


def _contact_cache_key(email):
    return f"digital_subscriptions:contact:{email}"


def _contact_lock_key(lock_key):
    return f"digital_subscriptions:contact_lock:{lock_key}"


def _acquire_lock(lock_key, timeout=30):
    try:
        return _cache_set(lock_key, "1", expires=timeout, only_if_missing=True)
    except Exception:
        try:
            if _cache_get(lock_key):
                return False
            _cache_set(lock_key, "1", expires=timeout)
            return True
        except Exception:
            frappe.log_error(
                f"Cache locking failed for key {lock_key}",
                "Digital Subscriptions Lock Error",
            )
            return True


def _release_lock(lock_key):
    _cache_delete(lock_key)


def _acquire_contact_lock(lock_key, timeout=CONTACT_LOCK_TIMEOUT):
    return _acquire_lock(_contact_lock_key(lock_key), timeout=timeout)


def _release_contact_lock(lock_key):
    _release_lock(_contact_lock_key(lock_key))


def _with_contact_lock(
    lock_key,
    func,
    timeout=CONTACT_LOCK_TIMEOUT,
    wait_timeout=CONTACT_LOCK_WAIT_TIMEOUT,
    sleep_interval=0.2,
    fallback=None,
):
    deadline = time.time() + wait_timeout
    acquired = False

    while time.time() <= deadline:
        acquired = bool(_acquire_contact_lock(lock_key, timeout=timeout))
        if acquired:
            break
        time.sleep(sleep_interval)

    if not acquired:
        _increment_contact_metric("lock_timeout")
        if fallback:
            logger.warning("Falling back after contact lock timeout for %s", lock_key)
            return fallback()
        raise frappe.ValidationError(f"Unable to acquire contact lock for {lock_key}")

    try:
        return func()
    finally:
        _release_contact_lock(lock_key)


def _resolve_user(user=None):
    if user:
        return user

    session = getattr(frappe, "session", None)
    session_user = getattr(session, "user", None)
    if session_user and session_user != "Guest":
        return session_user

    return None


def _get_user_doc(user):
    if not user:
        return None

    if hasattr(user, "doctype") and getattr(user, "doctype", None) == "User":
        return user

    return frappe.get_doc("User", user)


def _get_contact_fullname(user_doc):
    fullname = frappe.utils.get_fullname(user_doc.name).strip()
    if fullname:
        return fullname

    fallback_email = getattr(user_doc, "email", None) or getattr(user_doc, "name", None) or ""
    return fallback_email.split("@")[0].strip() or fallback_email


def _get_contact_first_name(user_doc):
    first_name = (getattr(user_doc, "first_name", None) or "").strip()
    if first_name:
        return first_name

    fullname = _get_contact_fullname(user_doc)
    return fullname.split(" ", 1)[0].strip() or fullname


def _invalidate_contact_cache(email):
    if email:
        _cache_delete(_contact_cache_key(email))


def _get_contact_by_email(email):
    if not email:
        return None

    cached_contact = _cache_get(_contact_cache_key(email))
    if cached_contact:
        return cached_contact

    contact_name = frappe.db.get_value("Contact", {"email_id": email}, "name")
    if contact_name:
        _cache_set(_contact_cache_key(email), contact_name, expires=CONTACT_CACHE_TTL)

    return contact_name


def _create_contact_safely(user_doc, ignore_links=False, ignore_mandatory=False):
    email = getattr(user_doc, "email", None) or getattr(user_doc, "name", None)

    contact = frappe.get_doc(
        {
            "doctype": "Contact",
            "first_name": _get_contact_first_name(user_doc),
            "last_name": getattr(user_doc, "last_name", None),
            "user": user_doc.name,
            "gender": getattr(user_doc, "gender", None),
        }
    )

    if email:
        contact.add_email(email, is_primary=True)

    if getattr(user_doc, "phone", None):
        contact.add_phone(user_doc.phone, is_primary_phone=True)

    if getattr(user_doc, "mobile_no", None):
        contact.add_phone(user_doc.mobile_no, is_primary_mobile_no=True)

    try:
        contact.insert(
            ignore_permissions=True,
            ignore_links=ignore_links,
            ignore_mandatory=ignore_mandatory,
        )
        _invalidate_contact_cache(email)
        _increment_contact_metric("created")
        logger.info("Created contact %s for user %s", contact.name, user_doc.name)
        return contact.name
    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        contact_name = _get_contact_by_email(email)
        if contact_name:
            _increment_contact_metric("deduplicated")
            return contact_name
        raise


def _update_contact_safely(contact_name, user_doc, ignore_links=False, ignore_mandatory=False):
    email = getattr(user_doc, "email", None) or getattr(user_doc, "name", None)

    try:
        contact = frappe.get_doc("Contact", contact_name)
    except frappe.DoesNotExistError:
        _invalidate_contact_cache(email)
        return _create_contact_safely(
            user_doc,
            ignore_links=ignore_links,
            ignore_mandatory=ignore_mandatory,
        )

    contact.first_name = _get_contact_first_name(user_doc)
    contact.last_name = getattr(user_doc, "last_name", None)
    contact.gender = getattr(user_doc, "gender", None)
    contact.user = user_doc.name

    if email and not any(row.email_id == email for row in contact.email_ids):
        contact.add_email(email, is_primary=not any(row.is_primary == 1 for row in contact.email_ids))

    if getattr(user_doc, "phone", None) and not any(
        row.phone == user_doc.phone for row in contact.phone_nos
    ):
        contact.add_phone(
            user_doc.phone,
            is_primary_phone=not any(row.is_primary_phone == 1 for row in contact.phone_nos),
        )

    if getattr(user_doc, "mobile_no", None) and not any(
        row.phone == user_doc.mobile_no for row in contact.phone_nos
    ):
        contact.add_phone(
            user_doc.mobile_no,
            is_primary_mobile_no=not any(
                row.is_primary_mobile_no == 1 for row in contact.phone_nos
            ),
        )

    try:
        contact.save(ignore_permissions=True)
        _invalidate_contact_cache(email)
        _increment_contact_metric("updated")
        return contact.name
    except frappe.TimestampMismatchError:
        frappe.db.rollback()
        frappe.db.set_value(
            "Contact",
            contact_name,
            {
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "gender": contact.gender,
                "user": contact.user,
            },
            update_modified=False,
        )
        _invalidate_contact_cache(email)
        _increment_contact_metric("timestamp_conflict")
        logger.warning("Resolved contact timestamp conflict for %s", contact_name)
        return contact_name
    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        existing_contact = _get_contact_by_email(email)
        if existing_contact:
            _increment_contact_metric("deduplicated")
            return existing_contact
        raise


def _get_party_primary_contact_field(doctype):
    return {
        "Customer": "customer_primary_contact",
        "Supplier": "supplier_primary_contact",
    }.get(doctype)


def _link_contact_to_party_safely(contact_name, doctype, party_name):
    if not contact_name or not doctype or not party_name:
        return contact_name

    if frappe.db.exists(
        "Dynamic Link",
        {
            "parenttype": "Contact",
            "parentfield": "links",
            "parent": contact_name,
            "link_doctype": doctype,
            "link_name": party_name,
        },
    ):
        _set_party_primary_contact(doctype, party_name, contact_name)
        return contact_name

    now = frappe.utils.now()
    owner = _resolve_user("Administrator") or "Administrator"
    next_idx = frappe.db.sql(
        """
        select coalesce(max(idx), 0) + 1
        from `tabDynamic Link`
        where parent = %s and parenttype = 'Contact' and parentfield = 'links'
        """,
        (contact_name,),
    )[0][0]

    frappe.db.sql(
        """
        insert into `tabDynamic Link`
            (
                name,
                creation,
                modified,
                modified_by,
                owner,
                docstatus,
                idx,
                parent,
                parentfield,
                parenttype,
                link_doctype,
                link_name,
                link_title
            )
        select
            %(name)s,
            %(creation)s,
            %(modified)s,
            %(modified_by)s,
            %(owner)s,
            0,
            %(idx)s,
            %(parent)s,
            'links',
            'Contact',
            %(link_doctype)s,
            %(link_name)s,
            %(link_title)s
        where not exists (
            select 1
            from `tabDynamic Link`
            where parent = %(parent)s
                and parenttype = 'Contact'
                and parentfield = 'links'
                and link_doctype = %(link_doctype)s
                and link_name = %(link_name)s
        )
        """,
        {
            "name": frappe.generate_hash(length=10),
            "creation": now,
            "modified": now,
            "modified_by": owner,
            "owner": owner,
            "idx": next_idx,
            "parent": contact_name,
            "link_doctype": doctype,
            "link_name": party_name,
            "link_title": party_name,
        },
    )

    _increment_contact_metric("linked")
    _set_party_primary_contact(doctype, party_name, contact_name)
    return contact_name


def _set_party_primary_contact(doctype, party_name, contact_name):
    primary_contact_field = _get_party_primary_contact_field(doctype)
    if not primary_contact_field:
        return

    current_value = frappe.db.get_value(doctype, party_name, primary_contact_field)
    if not current_value:
        frappe.db.set_value(doctype, party_name, primary_contact_field, contact_name, update_modified=False)


def _validate_function_signature(module, func_name, expected_args):
    function = getattr(module, func_name, None)
    if not callable(function):
        return False

    parameters = list(inspect.signature(function).parameters)
    return tuple(parameters[: len(expected_args)]) == tuple(expected_args)


def _create_safe_patch(original_func, patched_func):
    @functools.wraps(patched_func)
    def wrapper(*args, **kwargs):
        try:
            return patched_func(*args, **kwargs)
        except frappe.RetryBackgroundJobError:
            raise
        except Exception:
            logger.error(
                "Patched function %s failed, falling back to original.\n%s",
                getattr(patched_func, "__name__", "patched"),
                frappe.get_traceback(),
            )
            _increment_contact_metric(f"fallback_{getattr(patched_func, '__name__', 'patched')}")
            if original_func is None:
                raise
            return original_func(*args, **kwargs)

    wrapper._original = original_func
    return wrapper


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

    contact_name = _get_contact_by_email(user)
    if not contact_name:
        return None

    try:
        contact = frappe.get_doc("Contact", contact_name)
    except frappe.DoesNotExistError:
        _invalidate_contact_cache(user)
        return None

    for link in contact.links:
        if link.link_doctype == doctype and frappe.db.exists(doctype, link.link_name):
            return frappe.get_doc(doctype, link.link_name)

    return None


def create_customer_or_supplier(user=None):
    user = _resolve_user(user)
    if not user:
        return None

    if frappe.db.get_value("User", user, "user_type") != "Website User":
        return None

    user_roles = frappe.get_roles(user)
    portal_settings = frappe.get_single("Portal Settings")
    default_role = portal_settings.default_role

    if default_role not in ["Customer", "Supplier"]:
        return None

    doctype = default_role if default_role in user_roles else None
    if not doctype:
        return None

    existing_party = _get_existing_party_for_user(doctype, user)
    if existing_party:
        return existing_party

    lock_key = f"party_creation_lock:{user}:{doctype}"
    if not _acquire_lock(lock_key):
        time.sleep(0.5)
        existing_party = _get_existing_party_for_user(doctype, user)
        if existing_party:
            return existing_party
        time.sleep(0.5)
        if not _acquire_lock(lock_key):
            frappe.log_error(
                f"Could not acquire lock for {doctype} creation for user {user}",
                "Party Creation Lock Error",
            )
            return None

    logger.info("Creating %s for user %s", doctype, user)
    try:
        existing_party = _get_existing_party_for_user(doctype, user)
        if existing_party:
            logger.info("%s already exists for user %s: %s", doctype, user, existing_party.name)
            return existing_party

        fullname = frappe.utils.get_fullname(user).strip()
        if not fullname:
            fullname = user.split("@")[0]
            logger.warning("Empty name for user %s, using '%s'", user, fullname)

        alternate_doctype = "Customer" if doctype == "Supplier" else "Supplier"
        if _get_existing_party_for_user(alternate_doctype, user):
            fullname += f"-{doctype}"

        party = frappe.new_doc(doctype)
        if doctype == "Customer":
            party.update({"customer_name": fullname, "customer_type": "Individual"})
        else:
            party.update(
                {
                    "supplier_name": fullname,
                    "supplier_group": "All Supplier Groups",
                    "supplier_type": "Individual",
                }
            )

        party.append("portal_users", {"user": user})
        party.flags.ignore_mandatory = True
        party.flags.ignore_links = True
        party.insert(ignore_permissions=True)
        logger.info("%s created: %s ('%s') for user %s", doctype, party.name, fullname, user)

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
    user_doc = _get_user_doc(user)
    email = getattr(user_doc, "email", None) or user_doc.name
    lock_key = f"{email}:{doctype}:{party_name}"

    def _link_contact():
        contact_name = _get_contact_by_email(email)
        if contact_name:
            contact_name = _update_contact_safely(contact_name, user_doc)
        else:
            contact_name = _create_contact_safely(user_doc)

        return _link_contact_to_party_safely(contact_name, doctype, party_name)

    try:
        return _with_contact_lock(
            lock_key,
            _link_contact,
            fallback=lambda: _link_contact_to_party_safely(
                _get_contact_by_email(email), doctype, party_name
            ),
        )
    except frappe.QueryDeadlockError:
        frappe.db.rollback()
        _increment_contact_metric("deadlock")
        logger.warning(
            "Deadlock linking contact for %s and %s %s",
            email,
            doctype,
            party_name,
        )
        return None
    except Exception:
        _increment_contact_metric("link_error")
        frappe.log_error(
            f"Error in create_party_contact for {email}:\n{frappe.get_traceback()}",
            "Contact Link Error",
        )
        return None


@frappe.whitelist()
def contact_system_healthcheck():
    import frappe.core.doctype.user.user as user_module
    import erpnext.portal.utils as portal_utils

    metrics = {
        "created": _get_contact_metric("created"),
        "updated": _get_contact_metric("updated"),
        "linked": _get_contact_metric("linked"),
        "deadlock": _get_contact_metric("deadlock"),
        "timestamp_conflict": _get_contact_metric("timestamp_conflict"),
        "lock_timeout": _get_contact_metric("lock_timeout"),
    }

    return {
        "cache_available": bool(frappe.cache()),
        "patches": {
            "frappe_create_contact": getattr(user_module.create_contact, "__module__", "")
            == "digital_subscriptions",
            "erpnext_create_customer_or_supplier": getattr(
                portal_utils.create_customer_or_supplier, "__module__", ""
            )
            == "digital_subscriptions.overrides",
            "erpnext_create_party_contact": getattr(
                portal_utils.create_party_contact, "__module__", ""
            )
            == "digital_subscriptions.overrides",
        },
        "metrics": metrics,
    }


def create_primary_contact(self):
    if not self.customer_primary_contact and not self.lead_name:
        return _original_create_primary_contact(self)

    if not self.customer_primary_contact:
        return

    user_type = None
    if getattr(frappe, "session", None) and frappe.session.user:
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type")

    if user_type == "Website User":
        frappe.db.set_value(
            "Contact",
            self.customer_primary_contact,
            "is_primary_contact",
            1,
            update_modified=False,
        )
        return

    frappe.set_value("Contact", self.customer_primary_contact, "is_primary_contact", 1)