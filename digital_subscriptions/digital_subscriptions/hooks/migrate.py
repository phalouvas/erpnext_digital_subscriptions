import frappe
from frappe.exceptions import PermissionError
from frappe.core.doctype.user.user import create_contact
from erpnext.portal.utils import party_exists
from datetime import datetime, timedelta

@frappe.whitelist(allow_guest=False)
def create_users():
	if not frappe.session.user == "Administrator":
		raise PermissionError("Only the Administrator can perform the migration.")
	
	# Get all users from table `rc11v_users`
	users = frappe.db.sql("SELECT * FROM `rc11v_users`", as_dict=True)
	# For each user in `rc11v_users`, create a new user in `tabUser`
	for user in users:
		customer = create_customer(user)

		# Check if the user already exists in `tabUser`
		user_exists = frappe.get_all("User", filters={"email": user.email}, fields=["name"])
		if not user_exists:
			user_doc = frappe.get_doc({
				"doctype": "User",
				"email": user.email,
				"first_name": user.name,
				"username": user.username,
				"enabled": 1,
				"send_welcome_email": 0,
				"roles": [
					{
						"role": "Customer"
					}
				]
			}).insert()  
			frappe.db.commit()    
			contact = frappe.new_doc("Contact")
			contact.update({"first_name": user.name, "email_id": user.email})
			contact.append("links", dict(link_doctype="Customer", link_name=user.name))
			contact.append("email_ids", dict(email_id=user.email, is_primary=True))
			contact.flags.ignore_mandatory = True
			contact.insert(ignore_permissions=True)
			frappe.db.commit()
			if customer:
				customer.customer_primary_contact = contact.name
				customer.save(ignore_permissions=True)
				frappe.db.commit()
			create_contact(user_doc, ignore_links=True, ignore_mandatory=True)
			
		frappe.db.commit()
		link_customer(user.email)

	frappe.db.commit()
	return ["Migration completed successfully."]
	
def create_customer(user):
	doctype = "Customer"

	if party_exists(doctype, user.email):		
		return

	party = frappe.new_doc(doctype)
	fullname = user.name
	party.customer_name = fullname

	party.flags.ignore_mandatory = True
	party.insert(ignore_permissions=True)

	frappe.db.commit()

	return party

def link_customer(user):
	if frappe.db.get_value("User", user, "user_type") != "Website User":
		return

	doctype = "Customer"

	if party_exists(doctype, user):
		party = frappe.get_doc(doctype, {"email_id": user})
		if not frappe.db.exists("Portal User", {"user": user}):
			portal_user = frappe.new_doc("Portal User")
			portal_user.user = user
			party.append("portal_users", portal_user)
			fullname = frappe.utils.get_fullname(user)
			party.customer_name = fullname
			party.save(ignore_permissions=True)

@frappe.whitelist(allow_guest=False)
def create_subscriptions():
	if not frappe.session.user == "Administrator":
		raise PermissionError("Only the Administrator can perform the migration.")
	
	# Get all sales order with status "Completed" and "transaction_date" not older than 1 year
	one_year_ago = datetime.now() - timedelta(days=365)
	payments = frappe.db.sql(f"""
		SELECT 
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
		ORDER BY TPaymentEntry.posting_date
		LIMIT 10;
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
				"starts_on": payment.posting_date,
				"ends_one": payment.posting_Date + timedelta(days=365)
			}).insert()
			frappe.db.commit()

	return ["Subscriptions created successfully.", payments]