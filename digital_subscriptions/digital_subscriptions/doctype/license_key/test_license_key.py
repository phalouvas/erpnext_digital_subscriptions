# Copyright (c) 2026, KAINOTOMO PH LTD and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from digital_subscriptions.digital_subscriptions.doctype.license_key.license_key import (
	create_license_keys,
)


class _DummyLicenseKey:
	def __init__(self):
		self.flags = SimpleNamespace(ignore_permissions=False)
		self.saved = False
		self.name = "LIC-0001"

	def save(self, ignore_permissions=False):
		self.saved = True
		self.saved_with_ignore_permissions = ignore_permissions


class TestLicenseKey(FrappeTestCase):
	def test_license_key_generated_for_license_item(self):
		"""License Key is created when Payment Entry contains items in the license Item Group."""
		payment_entry = frappe._dict(
			doctype="Payment Entry",
			name="PE-0001",
			payment_type="Receive",
			references=[frappe._dict(reference_doctype="Sales Invoice", reference_name="SINV-0001")],
		)
		sales_invoice = frappe._dict(
			customer="CUST-0001",
			contact_email="customer@example.com",
			items=[frappe._dict(item_code="LIC-ITEM-1")],
		)
		item_doc = frappe._dict(item_code="LIC-ITEM-1", item_group="PH Agent Hub")

		created = []

		def fake_new_doc(doctype):
			self.assertEqual(doctype, "License Key")
			doc = _DummyLicenseKey()
			created.append(doc)
			return doc

		def fake_get_single(doctype):
			if doctype == "PH Agent Hub Settings":
				return frappe._dict(enabled=1, license_item_group="PH Agent Hub", license_duration_days=365)
			return frappe._dict()

		def fake_get_cached_doc(doctype, name):
			if doctype == "Item":
				return item_doc
			return frappe._dict()

		mock_key = frappe._dict(sign=lambda data: b"x" * 64)

		with patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_doc",
			return_value=sales_invoice,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_cached_doc",
			side_effect=fake_get_cached_doc,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_single",
			side_effect=fake_get_single,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_all",
			return_value=[],
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.new_doc",
			side_effect=fake_new_doc,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.sendmail",
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.ph_agent_hub_settings.ph_agent_hub_settings.PHAgentHubSettings.get_private_key",
			return_value=mock_key,
		):
			create_license_keys(payment_entry, method="on_submit")

		self.assertEqual(len(created), 1)
		self.assertTrue(created[0].saved)
		self.assertEqual(created[0].customer, "CUST-0001")
		self.assertEqual(created[0].item, "LIC-ITEM-1")
		self.assertEqual(created[0].payment_entry, "PE-0001")
		self.assertEqual(created[0].max_tenants, -1)

	def test_license_items_skipped_when_settings_disabled(self):
		"""No License Key is created when PH Agent Hub Settings are disabled."""
		payment_entry = frappe._dict(
			doctype="Payment Entry",
			name="PE-0002",
			payment_type="Receive",
			references=[frappe._dict(reference_doctype="Sales Invoice", reference_name="SINV-0002")],
		)
		sales_invoice = frappe._dict(
			customer="CUST-0002",
			items=[frappe._dict(item_code="LIC-ITEM-2")],
		)

		with patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_doc",
			return_value=sales_invoice,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_single",
			return_value=frappe._dict(enabled=0, license_item_group="PH Agent Hub"),
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.new_doc",
			side_effect=AssertionError("new_doc should not be called when settings disabled"),
		):
			create_license_keys(payment_entry, method="on_submit")

	def test_file_subscription_items_unaffected(self):
		"""Items NOT in the license Item Group are ignored — they still get File Subscriptions."""
		payment_entry = frappe._dict(
			doctype="Payment Entry",
			name="PE-0003",
			payment_type="Receive",
			references=[frappe._dict(reference_doctype="Sales Invoice", reference_name="SINV-0003")],
		)
		sales_invoice = frappe._dict(
			customer="CUST-0003",
			items=[frappe._dict(item_code="FILE-ITEM-1")],
		)
		item_doc = frappe._dict(item_code="FILE-ITEM-1", item_group="File Downloads")

		with patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_doc",
			return_value=sales_invoice,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_cached_doc",
			return_value=item_doc,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_single",
			return_value=frappe._dict(enabled=1, license_item_group="PH Agent Hub", license_duration_days=365),
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.new_doc",
			side_effect=AssertionError("new_doc should not be called for non-license items"),
		):
			create_license_keys(payment_entry, method="on_submit")

	def test_idempotency(self):
		"""Re-submitting the same Payment Entry does not create duplicate License Keys."""
		payment_entry = frappe._dict(
			doctype="Payment Entry",
			name="PE-0004",
			payment_type="Receive",
			references=[frappe._dict(reference_doctype="Sales Invoice", reference_name="SINV-0004")],
		)
		sales_invoice = frappe._dict(
			customer="CUST-0004",
			items=[frappe._dict(item_code="LIC-ITEM-4")],
		)
		item_doc = frappe._dict(item_code="LIC-ITEM-4", item_group="PH Agent Hub")

		with patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_doc",
			return_value=sales_invoice,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_cached_doc",
			return_value=item_doc,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_single",
			return_value=frappe._dict(enabled=1, license_item_group="PH Agent Hub", license_duration_days=365),
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_all",
			return_value=[{"name": "LIC-EXISTING"}],
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.new_doc",
			side_effect=AssertionError("new_doc should not be called for existing license keys"),
		):
			create_license_keys(payment_entry, method="on_submit")

	def test_email_failure_does_not_block(self):
		"""If email sending fails, the License Key is still saved."""
		payment_entry = frappe._dict(
			doctype="Payment Entry",
			name="PE-0005",
			payment_type="Receive",
			references=[frappe._dict(reference_doctype="Sales Invoice", reference_name="SINV-0005")],
		)
		sales_invoice = frappe._dict(
			customer="CUST-0005",
			contact_email="customer@example.com",
			items=[frappe._dict(item_code="LIC-ITEM-5")],
		)
		item_doc = frappe._dict(item_code="LIC-ITEM-5", item_group="PH Agent Hub")

		created = []

		def fake_new_doc(doctype):
			doc = _DummyLicenseKey()
			created.append(doc)
			return doc

		mock_key = frappe._dict(sign=lambda data: b"x" * 64)

		with patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_doc",
			return_value=sales_invoice,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_cached_doc",
			return_value=item_doc,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_single",
			return_value=frappe._dict(enabled=1, license_item_group="PH Agent Hub", license_duration_days=365),
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.get_all",
			return_value=[],
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.new_doc",
			side_effect=fake_new_doc,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.sendmail",
			side_effect=Exception("SMTP error"),
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.license_key.license_key.frappe.log_error",
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.ph_agent_hub_settings.ph_agent_hub_settings.PHAgentHubSettings.get_private_key",
			return_value=mock_key,
		):
			create_license_keys(payment_entry, method="on_submit")

		self.assertEqual(len(created), 1, "License Key should be saved even if email fails")
