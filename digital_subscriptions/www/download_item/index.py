import frappe
from frappe import _
import datetime

sitemap = 1


def get_context(context):
	name = frappe.form_dict.name
	context.subscription = frappe.get_doc("File Subscription", name)
	if context.subscription.ends_on < datetime.datetime.now():
		frappe.throw("Not allowed")
	context.item = frappe.get_doc("Item", context.subscription.item)
	context.title = context.item.item_name

	context.docs = []
	if (not context.subscription.disabled):
		versions = frappe.get_all(
				"File Version",
				filters={"item": context.item.name, "disabled": 0},
				fields=["version", "file", "changelog", "requirements", "release_type", "release_date"],
			)
			
		context.docs = versions

def is_file_shared(docname):
    # Query the DocShare table to check if the document is shared with the user
    shares = frappe.get_all(
        "DocShare",
        filters={"share_doctype": "File", "user": frappe.session.user, "share_name": docname},
        fields=["name"],
    )

    return len(shares) > 0

@frappe.whitelist(allow_guest=False)
def download_file():
	name = frappe.form_dict.name
	file = frappe.get_doc("File", name)
	if not is_file_shared(name):
		frappe.throw(_("Not allowed"))
	return get_file_content(file.file_url)
