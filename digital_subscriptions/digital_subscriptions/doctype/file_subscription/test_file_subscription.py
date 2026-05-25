# Copyright (c) 2023, KAINOTOMO PH LTD and Contributors
# See license.txt

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription import create_file_subscription


class _DummySubscription:
	def __init__(self):
		self.flags = SimpleNamespace(ignore_permissions=False)
		self.saved = False

	def save(self, ignore_permissions=False):
		self.saved = True
		self.saved_with_ignore_permissions = ignore_permissions


class TestFileSubscription(FrappeTestCase):
	def test_creates_one_subscription_per_eligible_item_for_multi_item_order(self):
		payment_entry = frappe._dict(
			doctype="Payment Entry",
			name="PE-0001",
			payment_type="Receive",
			references=[frappe._dict(reference_doctype="Sales Order", reference_name="SO-0001")],
		)
		sales_order = frappe._dict(
			customer="CUST-0001",
			items=[
				frappe._dict(item_code="ITEM-A"),
				frappe._dict(item_code="ITEM-B"),
				frappe._dict(item_code="ITEM-C"),
			],
		)

		created = []

		def fake_new_doc(doctype):
			self.assertEqual(doctype, "File Subscription")
			doc = _DummySubscription()
			created.append(doc)
			return doc

		def fake_get_all(doctype, filters=None, fields=None, limit=None):
			if doctype == "File Version":
				if filters["item"] in {"ITEM-A", "ITEM-C"} and filters["disabled"] == 0:
					return [{"name": f"FV-{filters['item']}"}]
				return []
			if doctype == "File Subscription":
				return []
			return []

		starts_on = datetime(2026, 4, 4, 10, 0, 0)
		ends_on = datetime(2027, 4, 4, 10, 0, 0)

		with patch("digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.get_doc", return_value=sales_order), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.new_doc",
			side_effect=fake_new_doc,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.utils.now_datetime",
			return_value=starts_on,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.utils.add_days",
			return_value=ends_on,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.get_single",
			return_value=frappe._dict(days=365),
		):
			create_file_subscription(payment_entry, method="on_submit")

		self.assertEqual(len(created), 2)
		self.assertTrue(all(doc.saved for doc in created))
		self.assertEqual({doc.item for doc in created}, {"ITEM-A", "ITEM-C"})
		self.assertEqual({doc.customer for doc in created}, {"CUST-0001"})
		self.assertEqual({doc.payment_entry for doc in created}, {"PE-0001"})
		self.assertEqual({doc.starts_on for doc in created}, {starts_on})
		self.assertEqual({doc.ends_on for doc in created}, {ends_on})

	def test_processes_all_payment_entry_references(self):
		payment_entry = frappe._dict(
			doctype="Payment Entry",
			name="PE-0002",
			payment_type="Receive",
			references=[
				frappe._dict(reference_doctype="Sales Order", reference_name="SO-0002"),
				frappe._dict(reference_doctype="Sales Invoice", reference_name="SINV-0001"),
			],
		)
		sales_order = frappe._dict(customer="CUST-0002", items=[frappe._dict(item_code="ITEM-1")])
		sales_invoice = frappe._dict(customer="CUST-0002", items=[frappe._dict(item_code="ITEM-2")])

		created = []

		def fake_get_doc(doctype, name):
			if doctype == "Sales Order" and name == "SO-0002":
				return sales_order
			if doctype == "Sales Invoice" and name == "SINV-0001":
				return sales_invoice
			self.fail(f"Unexpected get_doc call: {doctype} {name}")

		def fake_new_doc(_doctype):
			doc = _DummySubscription()
			created.append(doc)
			return doc

		with patch("digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.get_doc", side_effect=fake_get_doc), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.get_all",
			side_effect=lambda doctype, **kwargs: [{"name": "OK"}] if doctype == "File Version" else [],
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.new_doc",
			side_effect=fake_new_doc,
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.get_single",
			return_value=frappe._dict(days=365),
		):
			create_file_subscription(payment_entry, method="on_submit")

		self.assertEqual(len(created), 2)
		self.assertEqual({doc.item for doc in created}, {"ITEM-1", "ITEM-2"})

	def test_does_not_create_duplicate_subscription_for_same_payment_and_item(self):
		payment_entry = frappe._dict(
			doctype="Payment Entry",
			name="PE-0003",
			payment_type="Receive",
			references=[frappe._dict(reference_doctype="Sales Order", reference_name="SO-0003")],
		)
		sales_order = frappe._dict(customer="CUST-0003", items=[frappe._dict(item_code="ITEM-X")])

		with patch("digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.get_doc", return_value=sales_order), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.get_all",
			side_effect=lambda doctype, **kwargs: [{"name": "FV-X"}] if doctype == "File Version" else [{"name": "FS-EXISTING"}],
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.new_doc",
			side_effect=AssertionError("new_doc should not be called for existing subscriptions"),
		), patch(
			"digital_subscriptions.digital_subscriptions.doctype.file_subscription.file_subscription.frappe.get_single",
			return_value=frappe._dict(days=365),
		):
			create_file_subscription(payment_entry, method="on_submit")
