import frappe
from frappe.exceptions import PermissionError
from frappe.core.doctype.user.user import create_contact
from erpnext.portal.utils import party_exists
from datetime import datetime, timedelta

@frappe.whitelist(allow_guest=False)
def create_subscriptions():
	if not frappe.session.user == "Administrator":
		raise PermissionError("Only the Administrator can perform the migration.")
	
	# Get all sales order with status "Completed" and "transaction_date" not older than 1 year
	one_year_ago = datetime.now() - timedelta(days=365)
	payments = frappe.db.sql(f"""
		SELECT DISTINCT
			TPaymentEntry.name AS name,
			TPaymentEntry.party AS party,
			TPaymentEntryReference.reference_name AS reference_name,
			TPaymentEntryReference.reference_doctype AS reference_doctype,
			TPaymentEntry.posting_date AS posting_date,
			CASE
				WHEN TPaymentEntryReference.reference_doctype = 'Sales Invoice' THEN TFileVersion_invoice.item
				WHEN TPaymentEntryReference.reference_doctype = 'Sales Order' THEN TFileVersion_order.item
				ELSE NULL
			END AS item
		FROM `tabPayment Entry` AS TPaymentEntry
			LEFT JOIN `tabPayment Entry Reference` AS TPaymentEntryReference ON TPaymentEntry.name = TPaymentEntryReference.parent
			LEFT JOIN `tabSales Invoice` AS TSalesInvoice ON TPaymentEntryReference.reference_name = TSalesInvoice.name AND TPaymentEntryReference.reference_doctype = 'Sales Invoice'
			LEFT JOIN `tabSales Invoice Item` AS TSalesInvoiceItem ON TSalesInvoice.name = TSalesInvoiceItem.parent AND TPaymentEntryReference.reference_doctype = 'Sales Invoice'
			LEFT JOIN `tabFile Version` AS TFileVersion_invoice ON TSalesInvoiceItem.item_code = TFileVersion_invoice.item AND TPaymentEntryReference.reference_doctype = 'Sales Invoice'
			LEFT JOIN `tabSales Order` AS TSalesOrder ON TPaymentEntryReference.reference_name = TSalesOrder.name AND TPaymentEntryReference.reference_doctype = 'Sales Order'
			LEFT JOIN `tabSales Order Item` AS TSalesOrderItem ON TSalesOrder.name = TSalesOrderItem.parent AND TPaymentEntryReference.reference_doctype = 'Sales Order'
			LEFT JOIN `tabFile Version` AS TFileVersion_order ON TSalesOrderItem.item_code = TFileVersion_order.item AND TPaymentEntryReference.reference_doctype = 'Sales Order'
		WHERE TPaymentEntry.posting_date >= '{one_year_ago}'
			AND TPaymentEntry.payment_type = 'Receive'
			AND TPaymentEntry.docstatus = 1
			AND TPaymentEntry.party_type = 'Customer'
		ORDER BY TPaymentEntry.posting_date;
	""", as_dict=True)

	for payment in payments:
		# Check if the subscription already exists in `tabSubscription`
		if not payment.item:
			continue
		subscription_exists = frappe.get_all("File Subscription", filters={"item": payment.item, "payment_entry": payment.name}, fields=["name"])
		if not subscription_exists:
			frappe.get_doc({
				"doctype": "File Subscription",
				"customer": payment.party,
				"payment_entry": payment.name,
				"item": payment.item,
				"starts_on": payment.posting_date,
				"ends_on": payment.posting_date + timedelta(days=365)
			}).insert()
			frappe.db.commit()

	return ["Subscriptions created successfully."]