# Copyright (c) 2026, KAINOTOMO PH LTD and Contributors
# See license.txt

from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

import frappe

from digital_subscriptions import create_contact as unified_create_contact
from digital_subscriptions import frappe_user
from digital_subscriptions.overrides import _create_safe_patch
from digital_subscriptions.overrides import _link_contact_to_party_safely
from digital_subscriptions.overrides import _validate_function_signature
from digital_subscriptions.overrides import _with_contact_lock


class TestContactCoordinator(TestCase):
    def test_validate_function_signature(self):
        self.assertTrue(
            _validate_function_signature(
                frappe_user,
                "create_contact",
                ("user", "ignore_links", "ignore_mandatory"),
            )
        )
        self.assertFalse(_validate_function_signature(frappe_user, "create_contact", ("doc",)))

    def test_create_safe_patch_falls_back_to_original(self):
        original = Mock(return_value="original-result")

        def patched(*args, **kwargs):
            raise RuntimeError("boom")

        safe_patch = _create_safe_patch(original, patched)
        self.assertEqual(safe_patch("arg"), "original-result")
        original.assert_called_once_with("arg")

    def test_with_contact_lock_uses_fallback_after_timeout(self):
        with patch("digital_subscriptions.overrides._acquire_contact_lock", return_value=False), patch(
            "digital_subscriptions.overrides.time.sleep"
        ):
            result = _with_contact_lock(
                "lock-key",
                lambda: "primary",
                wait_timeout=0,
                fallback=lambda: "fallback",
            )

        self.assertEqual(result, "fallback")

    def test_link_contact_to_party_sets_primary_contact(self):
        db = Mock()
        db.exists.return_value = False
        db.sql.return_value = [[1]]
        db.get_value.return_value = None

        with patch.object(frappe, "db", db), patch("digital_subscriptions.overrides.frappe.generate_hash", return_value="DL-1"), patch(
            "digital_subscriptions.overrides.frappe.utils.now", return_value="2026-03-27 00:00:00"
        ), patch("digital_subscriptions.overrides._resolve_user", return_value="Administrator"):
            result = _link_contact_to_party_safely("CONTACT-1", "Customer", "CUST-1")

        self.assertEqual(result, "CONTACT-1")
        self.assertEqual(db.sql.call_count, 2)
        db.set_value.assert_called_once_with(
            "Customer", "CUST-1", "customer_primary_contact", "CONTACT-1", update_modified=False
        )

    def test_unified_create_contact_retries_deadlock(self):
        user_doc = frappe._dict(name="user@example.com", email="user@example.com", doctype="User")
        db = Mock()

        with patch("digital_subscriptions._with_contact_lock", side_effect=frappe.QueryDeadlockError), patch(
            "digital_subscriptions.frappe.get_doc", return_value=user_doc
        ), patch("digital_subscriptions.frappe.db", db):
            with self.assertRaises(frappe.RetryBackgroundJobError):
                unified_create_contact("user@example.com")

        db.rollback.assert_called_once_with()
