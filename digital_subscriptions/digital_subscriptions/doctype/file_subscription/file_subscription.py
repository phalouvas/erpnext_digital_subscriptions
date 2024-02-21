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
		reference = doc.references[0]
		doc_type = reference.reference_doctype
		doc_name = reference.reference_name

		if doc_type == "Sales Invoice" or doc_type == "Sales Order" or doc_type == "Quotation" or doc_type == "Delivery Note":
			doc_ref = frappe.get_doc(doc_type, doc_name)
			# Check if the doc_ref has only one item
			if len(doc_ref.items) == 1:
				item = doc_ref.items[0]
				# Check if there is and File Version for the item that is not disabled
				versions = frappe.get_all("File Version", filters={"item": item.item_code, "disabled": 0}, fields=["name"])
				first_version = versions[0] if versions else None
				if not first_version:
					return
				# Create file subscripion
				subscripion = frappe.new_doc('File Subscription')
				subscripion.customer = doc_ref.customer
				subscripion.item = item.item_code
				subscripion.payment_entry = doc.name
				subscripion.starts_on = frappe.utils.now_datetime()
				subscripion.ends_on = frappe.utils.add_days(subscripion.starts_on, 365)
				subscripion.flags.ignore_permissions = True
				subscripion.save(ignore_permissions=True)

	pass
