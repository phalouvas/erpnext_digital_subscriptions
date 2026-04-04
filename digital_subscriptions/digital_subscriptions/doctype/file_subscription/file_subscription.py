# Copyright (c) 2023, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FileSubscription(Document):
	pass

def create_file_subscription(doc, method=None, status=None):
	# Create a File Subscription for a Payment Entry
	if doc.doctype == "Payment Entry" and method == "on_submit" and doc.payment_type == "Receive":
		# Check if there are any references
		if not doc.references:
			return
		allowed_reference_doctypes = {"Sales Invoice", "Sales Order", "Quotation", "Delivery Note"}

		for reference in doc.references:
			doc_type = reference.reference_doctype
			doc_name = reference.reference_name

			if doc_type not in allowed_reference_doctypes or not doc_name:
				continue

			doc_ref = frappe.get_doc(doc_type, doc_name)

			for item in doc_ref.items:
				# Skip items without an active File Version.
				versions = frappe.get_all("File Version", filters={"item": item.item_code, "disabled": 0}, fields=["name"], limit=1)
				if not versions:
					continue

				existing_subscription = frappe.get_all(
					"File Subscription",
					filters={"payment_entry": doc.name, "item": item.item_code},
					fields=["name"],
					limit=1,
				)
				if existing_subscription:
					continue

				# Create one file subscription per eligible item.
				subscription = frappe.new_doc("File Subscription")
				subscription.customer = doc_ref.customer
				subscription.item = item.item_code
				subscription.payment_entry = doc.name
				subscription.starts_on = frappe.utils.now_datetime()
				subscription.ends_on = frappe.utils.add_days(subscription.starts_on, 365)
				subscription.flags.ignore_permissions = True
				subscription.save(ignore_permissions=True)

	pass
