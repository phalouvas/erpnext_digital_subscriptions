import frappe

def has_website_permission(doc, ptype, user, verbose=False):
    """
    Always allow access to Item Group
    """
    return True