__version__ = '2.3.1'

import frappe
from digital_subscriptions.overrides import create_customer_or_supplier
from digital_subscriptions.overrides import create_party_contact

# Monkey patch the original function
import erpnext.portal.utils
erpnext.portal.utils.create_customer_or_supplier = create_customer_or_supplier
erpnext.portal.utils.create_party_contact = create_party_contact
