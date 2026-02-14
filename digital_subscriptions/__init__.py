__version__ = '16.0.1'

import frappe
from digital_subscriptions.overrides import create_customer_or_supplier
from digital_subscriptions.overrides import create_party_contact
from digital_subscriptions.overrides import create_primary_contact

# Monkey patch the original function
import erpnext.portal.utils
erpnext.portal.utils.create_customer_or_supplier = create_customer_or_supplier
erpnext.portal.utils.create_party_contact = create_party_contact

from erpnext.selling.doctype.customer.customer import Customer as ERPNextCustomer
ERPNextCustomer.create_primary_contact = create_primary_contact
