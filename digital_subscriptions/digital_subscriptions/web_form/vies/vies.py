import requests
import frappe
from xml.etree import ElementTree as ET
from frappe.model.rename_doc import update_document_title, rename_doc

def get_context(context):
	# do your magic here
	pass

def validate_vies(doc, method):
	if doc.tax_id:
		doc.tax_category = None
		vat_number = doc.tax_id
		# Create the SOAP envelope
		envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
		<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
			<soapenv:Header/>
			<soapenv:Body>
				<urn:checkVat>
					<urn:countryCode>{vat_number[:2]}</urn:countryCode>
					<urn:vatNumber>{vat_number[2:]}</urn:vatNumber>
				</urn:checkVat>
			</soapenv:Body>
		</soapenv:Envelope>"""

		# Set the headers and body for the POST request
		headers = {'Content-Type': 'text/xml'}
		url = 'http://ec.europa.eu/taxation_customs/vies/services/checkVatService'

		# Make the SOAP request using frappe.request
		try:
			response = requests.post(url, headers=headers, data=envelope)
			# Check the response and parse the result
			if response.status_code == 200:
				# Extract the valid attribute from the SOAP response
				root = ET.fromstring(response.content)
				valid = root.find(".//{urn:ec.europa.eu:taxud:vies:services:checkVat:types}valid").text == "true"
				if valid:
					# VIES number is valid
					doc.tax_category = "VIES"
					quotation = frappe.get_all("Quotation", filters={
						"quotation_to": "Customer", 
						"party_name": doc.name, 
						"order_type": "Shopping Cart",
						"docstatus": "Draft"
						}, fields=["name"])
					if quotation:
						# Delete the quotation associated with the invalid VIES number
						quotation_name = quotation[0]['name']
						frappe.delete_doc("Quotation", quotation_name, ignore_permissions=True)
					frappe.msgprint('You entered a valid VIES number!!!', title='Success')
				else:
					# VIES number is invalid
					frappe.msgprint('Invalid VIES number', title='Error')
			else:
				# Error occurred while validating VIES number
				frappe.msgprint('Error occurred while validating VIES number', title='Error')
		except Exception as e:
			frappe.msgprint('Please try again with a valid VIES number', title='Error')

def create_customer_or_supplier():
	"""Based on the default Role (Customer, Supplier), create a Customer / Supplier.
	Called on_session_creation hook.
	"""
	user = frappe.session.user

	if frappe.db.get_value("User", user, "user_type") != "Website User":
		return

	user_roles = frappe.get_roles()
	portal_settings = frappe.get_single("Portal Settings")
	default_role = portal_settings.default_role

	if default_role not in ["Customer"]:
		return

	# get customer
	if portal_settings.default_role and portal_settings.default_role in user_roles:
		doctype = portal_settings.default_role
	else:
		doctype = None

	if not doctype:
		return

	contact_name = frappe.db.get_value("Contact", {"email_id": user})
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for link in contact.links:
			if link.link_doctype == doctype:
				party = frappe.get_doc(doctype, link.link_name)

	if not party:
		return

	if not frappe.db.exists("Portal User", {"user": user}):
		fullname = frappe.utils.get_fullname(user)
		if party.name != fullname:
			new_name = rename_doc(
				doctype = doctype, 
				old = party.name, 
				new = fullname, 
				force=False, 
				merge=False, 
				ignore_permissions = True, 
				ignore_if_exists = False, 
				show_alert = False,
				rebuild_search = True,
				doc = None,
				validate= True)
			party = frappe.get_doc(doctype, new_name)
		portal_user = frappe.new_doc("Portal User")
		portal_user.user = user
		party.append("portal_users", portal_user)
		party.customer_name = fullname
		party.save(ignore_permissions=True)

	return party
