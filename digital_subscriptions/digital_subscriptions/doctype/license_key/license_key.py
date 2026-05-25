# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import base64
import json
from datetime import datetime, timedelta, timezone

import frappe
from frappe.model.document import Document

from digital_subscriptions.digital_subscriptions.doctype.ph_agent_hub_settings.ph_agent_hub_settings import (
	PHAgentHubSettings,
)


class LicenseKey(Document):
	def validate(self):
		"""Auto-generate the license key if not already set and settings are configured."""
		if self.license_key:
			return

		settings = frappe.get_single("PH Agent Hub Settings")
		if not settings.get("enabled") or not settings.get("private_key"):
			return

		private_key = PHAgentHubSettings.get_private_key()
		expiry_days = settings.get("license_duration_days", 365)

		license_key_str = _generate_license_key(
			private_key=private_key,
			sub=self.customer_email,
			max_tenants=self.max_tenants,
			expiry_days=expiry_days,
		)
		self.license_key = license_key_str

		# Parse payload back for audit fields
		payload = _decode_payload(license_key_str)
		if payload:
			self.max_tenants = payload.get("max_tenants", -1)
			self.expiry_date = payload.get("exp")
			self.issued_on = payload.get("iat")


def create_license_keys(doc, method=None, status=None):
	"""Create License Keys for license items when a Payment Entry is submitted.

	Follows the same pattern as `create_file_subscription` in `file_subscription.py`.
	Items belonging to the configured License Item Group in PH Agent Hub Settings
	trigger automatic Ed25519-signed license key generation.
	"""
	if doc.doctype != "Payment Entry" or method != "on_submit" or doc.payment_type != "Receive":
		return

	settings = frappe.get_single("PH Agent Hub Settings")
	if not settings.get("enabled") or not settings.get("license_item_group"):
		return

	if not doc.references:
		return

	allowed_reference_doctypes = {"Sales Invoice", "Sales Order", "Quotation", "Delivery Note"}

	for reference in doc.references:
		doc_type = reference.reference_doctype
		doc_name = reference.reference_name

		if doc_type not in allowed_reference_doctypes or not doc_name:
			continue

		doc_ref = frappe.get_doc(doc_type, doc_name)

		for item in doc_ref.items:
			# Check if the item belongs to the configured license Item Group
			item_doc = frappe.get_cached_doc("Item", item.item_code)
			if item_doc.item_group != settings.license_item_group:
				continue

			# Idempotency: skip if a License Key already exists for this payment + item
			existing = frappe.get_all(
				"License Key",
				filters={"payment_entry": doc.name, "item": item.item_code},
				fields=["name"],
				limit=1,
			)
			if existing:
				continue

			# Resolve customer email
			customer_email = _resolve_customer_email(doc_ref)

			# Build and sign the license payload
			private_key = PHAgentHubSettings.get_private_key()
			license_key_str = _generate_license_key(
				private_key=private_key,
				sub=customer_email,
				max_tenants=-1,
				expiry_days=settings.get("license_duration_days", 365),
			)

			# Parse payload back for audit fields
			payload = _decode_payload(license_key_str)

			# Create License Key document
			license_doc = frappe.new_doc("License Key")
			license_doc.customer = doc_ref.customer
			license_doc.customer_email = customer_email
			license_doc.item = item.item_code
			license_doc.payment_entry = doc.name
			license_doc.reference_doctype = doc_type
			license_doc.reference_name = doc_name
			license_doc.license_key = license_key_str
			license_doc.max_tenants = payload.get("max_tenants", -1)
			license_doc.expiry_date = payload.get("exp")
			license_doc.issued_on = payload.get("iat")
			license_doc.flags.ignore_permissions = True
			license_doc.save(ignore_permissions=True)

			# Send email — wrapped in try/except to prevent payment flow failures
			_send_license_email(license_doc, customer_email)


def _resolve_customer_email(doc_ref):
	"""Resolve the customer email from a Sales Invoice, Sales Order, etc."""
	customer_email = doc_ref.get("contact_email")
	if customer_email:
		return customer_email

	# Fallback: try to get primary contact email
	customer_name = doc_ref.get("customer")
	if customer_name:
		primary_contact = frappe.get_value("Customer", customer_name, "customer_primary_contact")
		if primary_contact:
			contact_email = frappe.get_value("Contact", primary_contact, "email_id")
			if contact_email:
				return contact_email

	return customer_name or "unknown@example.com"


def _generate_license_key(private_key, sub, max_tenants=-1, expiry_days=365):
	"""Generate an Ed25519-signed license key string.

	Format: {base64url_signature}.{base64url_payload}

	Args:
		private_key: Ed25519PrivateKey instance.
		sub: Licensee identifier (email or name).
		max_tenants: Maximum tenants (-1 for unlimited).
		expiry_days: Number of days until expiry.

	Returns:
		str: The license key in ``signature.payload`` format.
	"""
	now = datetime.now(timezone.utc)
	expires_on = now + timedelta(days=expiry_days)

	payload = {
		"v": 1,
		"sub": sub,
		"max_tenants": max_tenants,
		"exp": expires_on.strftime("%Y-%m-%dT%H:%M:%SZ"),
		"iat": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
	}

	payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
	payload_b64 = _base64url_encode(payload_json.encode("utf-8"))

	signature = private_key.sign(payload_json.encode("utf-8"))
	signature_b64 = _base64url_encode(signature)

	return f"{signature_b64}.{payload_b64}"


def _decode_payload(license_key_str):
	"""Decode and return the payload dict from a license key string."""
	try:
		payload_b64 = license_key_str.split(".")[1]
		# Pad for base64url decoding
		padded = payload_b64 + "=" * (4 - len(payload_b64) % 4) if len(payload_b64) % 4 else payload_b64
		payload_json = base64.urlsafe_b64decode(padded).decode("utf-8")
		return json.loads(payload_json)
	except (IndexError, ValueError, json.JSONDecodeError):
		return {}


def _base64url_encode(data):
	"""Base64url-encode bytes without padding."""
	return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _send_license_email(license_doc, recipient_email):
	"""Send the generated license key to the customer via email."""
	try:
		subject = "Your PH Agent Hub License Key"
		message = f"""<p>Thank you for your purchase.</p>

<p>Your PH Agent Hub License Key is:</p>

<pre style="background:#f5f5f5;padding:15px;border-radius:4px;font-size:14px;word-break:break-all;">{license_doc.license_key}</pre>

<p><strong>Expiry:</strong> {license_doc.expiry_date}</p>

<h4>How to Activate</h4>
<ol>
 <li>Log in to your PH Agent Hub Admin panel</li>
 <li>Go to <strong>Settings → License Key</strong></li>
 <li>Enter the license key above and save</li>
</ol>

<p>Need to renew? Visit our webshop at <a href="https://kainotomo.com">kainotomo.com</a>.</p>
"""

		frappe.sendmail(
			recipients=[recipient_email],
			subject=subject,
			message=message,
			reference_doctype="License Key",
			reference_name=license_doc.name,
		)
	except Exception:
		frappe.log_error(
			title="License Key Email Failed",
			message=f"Failed to send license key email for {license_doc.name} to {recipient_email}",
		)
