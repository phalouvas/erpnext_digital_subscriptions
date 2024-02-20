import frappe

@frappe.whitelist(Allow_guest=False)
def migrate():
    if not frappe.session.user == "Administrator":
        raise frappe.PermissionError("Only the Administrator can perform the migration.")
    
    # Your migration code here