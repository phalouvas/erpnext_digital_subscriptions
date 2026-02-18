__version__ = '16.0.3'

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

# Monkey patch webshop's update_debtors_account if webshop is installed
# This ensures digital_subscriptions handles all customer creation
try:
    if 'webshop' in frappe.get_installed_apps():
        import webshop.webshop.utils.portal as webshop_portal
        original_update_debtors_account = webshop_portal.update_debtors_account

        def patched_update_debtors_account():
            """
            Redirect webshop's customer creation to digital_subscriptions.
            This prevents duplicate customer creation when both hooks run.
            """
            # Call digital_subscriptions' version which will use webshop's
            # centralized service if available
            from digital_subscriptions.overrides import create_customer_or_supplier
            return create_customer_or_supplier()

        webshop_portal.update_debtors_account = patched_update_debtors_account
        frappe.logger("digital_subscriptions").info(
            "Monkey-patched webshop.update_debtors_account to use digital_subscriptions"
        )
except Exception as e:
    frappe.logger("digital_subscriptions").error(
        f"Failed to monkey-patch webshop.update_debtors_account: {str(e)}"
    )
