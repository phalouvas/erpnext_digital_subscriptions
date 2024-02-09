import frappe

@frappe.whitelist(allow_guest=False)
def download():
    pass