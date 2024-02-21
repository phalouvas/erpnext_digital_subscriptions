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
	data = frappe.db.sql(f"""
		SELECT 
			TItem.name AS item_name,
			TOrder.transaction_date AS order_date,
			TOrder.name AS order_name,
			TOrder.customer AS customer
		FROM `tabSales Order Item` AS TOrderItem
			LEFT JOIN `tabSales Order` AS TOrder ON TOrderItem.parent = TOrder.name
			LEFT JOIN `tabItem` AS TItem ON TOrderItem.item_code = TItem.item_code
			LEFT JOIN `tabItem Group` AS TItemGroup ON TItem.item_group = TItemGroup.name
		WHERE TOrder.transaction_date >= '{one_year_ago}'
			AND TOrder.status = 'Completed'
			AND TItemGroup.name = 'Joomla! Extensions Shop'
		ORDER BY TOrder.transaction_date
		LIMIT 1;
	""", as_dict=True)

	for order in data:
		# Check if the subscription already exists in `tabSubscription`
		subscription_exists = frappe.get_all("File Subscription", filters={"item": order.item_name, "sales_invoice": order.invoice_name}, fields=["name"])
		if not subscription_exists:
			subscription_doc = frappe.get_doc({
				"doctype": "Subscription",
				"subscription_name": order.item_name,
				"customer": order.customer,
				"start_date": order.order_date,
				"end_date": order.order_date + timedelta(days=365),
				"status": "Active",
				"billing_interval": "Yearly",
				"billing_period": 1,
				"billing_cycle": 1
			}).insert()
			frappe.db.commit()

	return ["Subscriptions created successfully.", data]