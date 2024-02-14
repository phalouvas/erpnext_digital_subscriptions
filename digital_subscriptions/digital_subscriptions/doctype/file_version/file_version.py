# Copyright (c) 2023, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import os
from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file
from urllib.parse import quote
import mimetypes
import datetime

from frappe.model.document import Document

class FileVersion(Document):
    def autoname(self):
        # Get the item_name from item
        item_name = frappe.get_value("Item", self.item, "item_name")
        self.name = f"{item_name} v{self.version}"

@frappe.whitelist(allow_guest=False)
def download():    
    if frappe.session.user == "Guest":
        frappe.throw(_("You don't have permission to access this file"), frappe.PermissionError)
    
    subscription = frappe.request.args.get("subscription")
    if not subscription:
        frappe.throw(_("Subscription not found"), frappe.DoesNotExistError)
    subscription = frappe.get_doc("File Subscription", subscription)
    if subscription.ends_on < datetime.datetime.now() or subscription.disabled:
          frappe.throw("Not allowed", frappe.PermissionError)
            
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

    response = send_private_file(version.file.split("/private", 1)[1])    
    return response
    
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
