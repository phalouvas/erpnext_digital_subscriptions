# Copyright (c) 2023, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import os
from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file
from urllib.parse import quote, unquote
import mimetypes
import datetime
import xml.etree.ElementTree as ET
import hashlib

from frappe.model.document import Document

class FileVersion(Document):
	def autoname(self):
		# Get the item_name from item
		item_name = frappe.get_value("Item", self.item, "item_name")
		self.name = f"{item_name} v{self.version}"

	def before_save(self):
		path = self.file.split("/private", 1)[1]
		path = os.path.join(frappe.local.conf.get("private_path", "private"), path.strip("/"))
		filepath = frappe.utils.get_site_path(path)
		with open(filepath, 'rb') as file:
			self.sha256 = hashlib.sha256(file.read()).hexdigest()

@frappe.whitelist(allow_guest=True)
def download():    
	
	version = frappe.request.args.get("version")
	if not version:
		frappe.throw(_("Version not found"), frappe.DoesNotExistError)
	version = frappe.get_doc("File Version", version)
	if version.disabled:
		frappe.throw(_("Version is disabled"), frappe.PermissionError)

	if not version.is_free:
		user = frappe.session.user
		if not user or user == "Guest":
			frappe.throw(_("Not allowed"), frappe.PermissionError)
		# Accept either 'subscription' or 'dlid' as the subscription identifier
		subscription = frappe.request.args.get("subscription") or frappe.request.args.get("dlid")
		if not subscription:
			frappe.throw(_("Subscription not found"), frappe.DoesNotExistError)
		subscription = frappe.get_doc("File Subscription", subscription)
		if subscription.ends_on < datetime.datetime.now() or subscription.disabled:
			frappe.throw("Not allowed", frappe.PermissionError)
		customer_names = frappe.db.get_all("Portal User", filters={"user": user, "parenttype": "Customer"}, fields=["parent"])
		customer_name = customer_names[0].parent if customer_names else None
		if subscription.customer != customer_name:
			frappe.throw(_("Not allowed"), frappe.PermissionError)

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

	# Set the filename for the downloaded file
	response.headers.add("Content-Disposition", "attachment", filename=filename)

	response.mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"

	return response

@frappe.whitelist(allow_guest=True)
def xml():
	# dlid can be either a subscription id (paid) or a free token (FREE-<item_code>)
	dlid = frappe.request.args.get("dlid")
	if not dlid:
		frappe.throw(_("Subscription not found"), frappe.DoesNotExistError)

	item = None
	use_free_mode = False

	# First, try resolving dlid as a File Subscription (paid flow)
	if frappe.db.exists("File Subscription", dlid):
		subscription = frappe.get_doc("File Subscription", dlid)
		if subscription.ends_on < datetime.datetime.now() or subscription.disabled:
			frappe.throw("Subscription expired", frappe.PermissionError)
		item = frappe.get_doc("Item", subscription.item)
		free_filter = {}
		free_dlid_value = dlid  # echo back whatever the client used
	else:
		# If not a subscription, check if it's a FREE token of the form FREE-<item_code>
		if isinstance(dlid, str) and dlid.startswith("FREE-"):
			item_code = dlid[len("FREE-"):]
			# item_code in ERPNext is typically the Item's name
			try:
				item = frappe.get_doc("Item", item_code)
			except Exception:
				item = None
			if not item:
				frappe.throw(_("Item not found for free dlid"), frappe.DoesNotExistError)
			use_free_mode = True
			free_filter = {"is_free": 1}
			free_dlid_value = dlid
		else:
			# Unknown dlid format
			frappe.throw(_("Invalid dlid"), frappe.DoesNotExistError)

	# Collect versions for the item; include only free when in free mode
	filters = {"item": item.name, "disabled": 0}
	filters.update(free_filter)
	versions = frappe.get_all(
			"File Version",
			filters=filters,
			fields=["name", "version", "file", "changelog", "requirements", "release_type", "release_date", "element", "type", "client", "target_platform", "sha256"],
			order_by="release_date desc",
		)

	# Convert versions to XML format
	xml_string = "<updates>"
	for version in versions:
		update_element = ET.Element("update")
		name_element = ET.SubElement(update_element, "name")
		name_element.text = item.item_name
		description_element = ET.SubElement(update_element, "description")
		description_element.text = item.description
		element_element = ET.SubElement(update_element, "element")
		element_element.text = version.element
		type_element = ET.SubElement(update_element, "type")
		type_element.text = version.type
		client_element = ET.SubElement(update_element, "client")
		client_element.text = version.client
		version_element = ET.SubElement(update_element, "version")
		version_element.text = version.version		
		downloads_element = ET.SubElement(update_element, "downloads")
		downloadurl_element = ET.SubElement(downloads_element, "downloadurl")
		downloadurl_element.set("type", "upgrade")
		downloadurl_element.set("format", "zip")
		# Always emit dlid in the URL to comply with Joomla extensions
		downloadurl_element.text = f"{frappe.utils.get_url()}/api/method/digital_subscriptions.digital_subscriptions.doctype.file_version.file_version.phrs_download?dlid={quote(free_dlid_value)}{quote('&')}version={quote(version.name)}"
		maintainer_element = ET.SubElement(update_element, "maintainer")
		maintainer_element.text = "KAINOTOMO PH LTD"
		maintainerurl_element = ET.SubElement(update_element, "maintainerurl")
		maintainerurl_element.text = "https://kainotomo.com"
		targetplatform_element = ET.SubElement(update_element, "targetplatform")
		targetplatform_element.set("name", "joomla")
		targetplatform_element.set("version", version.target_platform)
		checksum_element = ET.SubElement(update_element, "sha256")
		checksum_element.text = version.sha256
		xml_string += ET.tostring(update_element, encoding="unicode")
	xml_string += "</updates>"

	response = Response()
	response.data = xml_string
	response.mimetype = "application/xml"
	return response

@frappe.whitelist(allow_guest=True)
def phrs_download():  

	raw_query_string = frappe.request.environ.get('QUERY_STRING', '')
	decoded_query_string = unquote(raw_query_string)
	parameters = decoded_query_string.split('&')
	version = None
	subscription = None
	dlid = None
	for param in parameters:
		# split only on the first = to avoid breaking values containing =
		if '=' not in param:
			continue
		key, value = param.split('=', 1)
		if key == 'version':
			version = value
		elif key == 'subscription':
			subscription = value
		elif key == 'dlid':
			dlid = value
	
	if not version:
		frappe.throw(_("Version not found"), frappe.DoesNotExistError)
	version = frappe.get_doc("File Version", version)
	if version.disabled:
		frappe.throw(_("Version is disabled"), frappe.PermissionError)

	# Allow free versions without subscription/dlid
	if getattr(version, "is_free", 0):
		response = send_private_file(version.file.split("/private", 1)[1])
		return response

	# Paid versions require a valid subscription, accept either 'subscription' or 'dlid'
	subscription_or_dlid = subscription or dlid
	if not subscription_or_dlid:
		frappe.throw(_("Subscription not found"), frappe.DoesNotExistError)
	# Reject free dlid tokens for paid versions
	if isinstance(subscription_or_dlid, str) and subscription_or_dlid.startswith("FREE-"):
		frappe.throw("Not allowed", frappe.PermissionError)

	subscription_doc = frappe.get_doc("File Subscription", subscription_or_dlid)
	if subscription_doc.ends_on < datetime.datetime.now() or subscription_doc.disabled:
		frappe.throw("Not allowed", frappe.PermissionError)

	response = send_private_file(version.file.split("/private", 1)[1])    
	return response