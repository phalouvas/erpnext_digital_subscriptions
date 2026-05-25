# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import base64

import frappe
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import UnsupportedAlgorithm
from frappe.model.document import Document


class PHAgentHubSettings(Document):
	def validate(self):
		"""Derive and display the public key from the private key on save."""
		if not self.private_key:
			return

		key = self._load_private_key()
		if key is None:
			return

		public_key = key.public_key()
		public_key_pem = public_key.public_bytes(
			encoding=serialization.Encoding.PEM,
			format=serialization.PublicFormat.SubjectPublicKeyInfo,
		)
		self.public_key_display = public_key_pem.decode("utf-8").strip()

	@staticmethod
	def get_private_key():
		"""Load and return the Ed25519 private key object from settings.

		Returns:
			ed25519.Ed25519PrivateKey or None if not configured.

		Raises:
			frappe.ValidationError: If the private key is invalid.
		"""
		settings = frappe.get_single("PH Agent Hub Settings")
		if not settings.get("private_key"):
			frappe.throw("PH Agent Hub Settings: Ed25519 Private Key is not configured.", frappe.ValidationError)

		return PHAgentHubSettings._load_private_key_from_string(settings.get_password("private_key"))

	def _load_private_key(self):
		"""Load private key from the document's stored password value."""
		try:
			key_pem = self.get_password("private_key")
		except Exception:
			return None
		if not key_pem:
			return None
		return self._load_private_key_from_string(key_pem)

	@staticmethod
	def _load_private_key_from_string(key_str):
		"""Try to load key as PEM first, then as raw base64."""
		# Try PEM format first
		try:
			private_key = serialization.load_pem_private_key(key_str.encode("utf-8"), password=None)
			if isinstance(private_key, ed25519.Ed25519PrivateKey):
				return private_key
		except (ValueError, TypeError, UnsupportedAlgorithm):
			pass

		# Try raw base64-encoded 32-byte seed
		try:
			raw_bytes = base64.b64decode(key_str)
			if len(raw_bytes) == 32:
				return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
		except Exception:
			pass

		# Try base64url-encoded 32-byte seed
		try:
			raw_bytes = base64.urlsafe_b64decode(key_str + "==")
			if len(raw_bytes) == 32:
				return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
		except Exception:
			pass

		frappe.throw(
			"PH Agent Hub Settings: Invalid Ed25519 Private Key. "
			"Provide a PEM-encoded key or a raw base64 32-byte seed.",
			frappe.ValidationError,
		)
