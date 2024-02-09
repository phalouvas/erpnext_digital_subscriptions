import frappe
from frappe import _
import datetime

sitemap = 1


def get_context(context):
	name = frappe.form_dict.name
	context.subscription = frappe.get_doc("File Subscription", name)
	if context.subscription.ends_on < datetime.datetime.now() or context.subscription.disabled:
		frappe.throw("Not allowed", frappe.PermissionError)
	context.item = frappe.get_doc("Item", context.subscription.item)
	context.title = context.item.item_name

	context.docs = []
	if (not context.subscription.disabled):
		versions = frappe.get_all(
				"File Version",
				filters={"item": context.item.name, "disabled": 0},
				fields=["name", "version", "file", "changelog", "requirements", "release_type", "release_date"],
				order_by="release_date desc",
			)
			
		context.docs = versions

	context.no_cache = 0
	context.parents = [{"name": _("Home"), "route": "/"}, {"name": _("Download List"), "route": "/download_list"}]

def is_file_shared(docname):
    # Query the DocShare table to check if the document is shared with the user
    shares = frappe.get_all(
        "DocShare",
        filters={"share_doctype": "File", "user": frappe.session.user, "share_name": docname},
        fields=["name"],
    )

    return len(shares) > 0
