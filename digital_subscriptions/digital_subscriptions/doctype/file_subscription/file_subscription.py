# Copyright (c) 2023, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FileSubscription(Document):
	pass

def create_file_subscription(doc, method=None, status=None):
	if status == "Completed" and method == "on_payment_authorized":
		# Get the document details
		doc_type = doc.reference_doctype
		doc_name = doc.reference_name

		# Create a Delivery Note for Sales Orders
		if doc_type == "Sales Order":
			sales_order = frappe.get_doc("Sales Order", doc_name)
			if sales_order.order_type == "Shopping Cart":
				for item in sales_order.items:
					# Create file subscripion
					subscripion = frappe.new_doc('File Subscription')
					subscripion.customer = sales_order.customer
					subscripion.item = item.item_code
					subscripion.sales_order = sales_order.name
					subscripion.starts_on = frappe.utils.now_datetime()
					subscripion.ends_on = frappe.utils.add_days(subscripion.starts_on, 365)
					subscripion.flags.ignore_permissions = True
					subscripion.save(ignore_permissions=True)

	pass
