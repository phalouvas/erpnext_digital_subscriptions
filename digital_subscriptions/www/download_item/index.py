import frappe
from frappe import _
import datetime

sitemap = 1


def get_context(context):
	name = frappe.form_dict.name
	if name:
		context.subscription = frappe.get_doc("File Subscription", name)
		if context.subscription.ends_on < datetime.datetime.now() or context.subscription.disabled:
			frappe.throw("Not allowed", frappe.PermissionError)
		context.item = frappe.get_doc("Item", context.subscription.item)
		context.free_mode = False
	else:
		context.item = frappe.get_doc("Item", frappe.form_dict.item)
		context.subscription = {"name": None}
		context.free_mode = True
		# Provide a free dlid token for Joomla-style URLs
		context.free_dlid = f"FREE-{context.item.name}"

	context.title = context.item.item_name

	filters = {"item": context.item.name, "disabled": 0}
	if getattr(context, "free_mode", False):
		# In public (no subscription) view, only list free versions
		filters["is_free"] = 1

	context.docs = frappe.get_all(
		"File Version",
		filters=filters,
		fields=[
			"name",
			"version",
			"file",
			"changelog",
			"requirements",
			"release_type",
			"release_date",
			"is_free",
		],
		order_by="release_date desc",
	)

	# Expose if any free versions available (useful for conditional DLID display)
	context.has_free = len(context.docs) > 0

	context.no_cache = 1
	context.parents = [{"name": _("Home"), "route": "/"}, {"name": _("Download List"), "route": "/download_list"}]

def is_file_shared(docname):
    # Query the DocShare table to check if the document is shared with the user
    shares = frappe.get_all(
        "DocShare",
        filters={"share_doctype": "File", "user": frappe.session.user, "share_name": docname},
        fields=["name"],
    )

    return len(shares) > 0
