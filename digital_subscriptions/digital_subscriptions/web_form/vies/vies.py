import requests
import frappe
from xml.etree import ElementTree as ET

def get_context(context):
	# do your magic here
	pass

@frappe.whitelist(allow_guest=False)
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
						frappe.msgprint('You entered a valid VIES number!!!', title='Success')
					else:
						# VIES number is invalid
						frappe.msgprint('Invalid VIES number', title='Error')
				else:
					# Error occurred while validating VIES number
					frappe.msgprint('Error occurred while validating VIES number', title='Error')
			except Exception as e:
				frappe.msgprint('Please try again with a valid VIES number', title='Error')
