__version__ = '16.0.4'

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

# Monkey patch webshop's update_debtors_account.
# Webshop + digital_subscriptions are expected to be installed together.
try:
    import webshop.webshop.utils.portal as webshop_portal

    def patched_update_debtors_account():
        return create_customer_or_supplier()

    webshop_portal.update_debtors_account = patched_update_debtors_account
    frappe.logger("digital_subscriptions").info(
        "Monkey-patched webshop.update_debtors_account to use digital_subscriptions"
    )
except ImportError:
    pass
