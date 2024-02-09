import frappe
from frappe import _
import os
from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file
from urllib.parse import quote
import mimetypes

def get_context(context):    
    if frappe.session.user == "Guest":
        frappe.throw(_("You don't have permission to access this file"), frappe.PermissionError)
    
    subscription = frappe.request.args.get("subscription")
    if not subscription:
        frappe.throw(_("Subscription not found"), frappe.DoesNotExistError)
    subscription = frappe.get_doc("File Subscription", subscription)
    # get customer user
    customer = frappe.get_doc("Customer", subscription.customer)
    is_allowed = False
    for portal_user in customer.portal_users:
        if portal_user.user == frappe.session.user:
            is_allowed = True
            break
    if not is_allowed:
        frappe.throw(_("You don't have permission to access this file"), frappe.PermissionError)

    version = frappe.request.args.get("version")
    if not version:
        frappe.throw(_("Version not found"), frappe.DoesNotExistError)
    version = frappe.get_doc("File Version", version)
    if version.disabled:
        frappe.throw(_("Version is disabled"), frappe.PermissionError)

    return send_private_file(version.file.split("/private", 1)[1])
    
def send_private_file(path: str) -> Response:
	path = os.path.join(frappe.local.conf.get("private_path", "private"), path.strip("/"))
	filename = os.path.basename(path)

	if frappe.local.request.headers.get("X-Use-X-Accel-Redirect"):
		path = "/protected/" + path
		response = Response()
		response.headers["X-Accel-Redirect"] = quote(frappe.utils.encode(path))

	else:
		filepath = frappe.utils.get_site_path(path)
		try:
			f = open(filepath, "rb")
		except OSError:
			frappe.throw(_("File not found"), frappe.DoesNotExistError)

		response = Response(wrap_file(frappe.local.request.environ, f), direct_passthrough=True)

	# no need for content disposition and force download. let browser handle its opening.
	# Except for those that can be injected with scripts.

	extension = os.path.splitext(path)[1]
	blacklist = [".svg", ".html", ".htm", ".xml"]

	if extension.lower() in blacklist:
		response.headers.add("Content-Disposition", "attachment", filename=filename)

	response.mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"

	return response