# Copilot Instructions for `digital_subscriptions`

- **What this app is**: Frappe/ERPNext app for selling downloadable files. Core DocTypes live under [digital_subscriptions/digital_subscriptions/doctype](digital_subscriptions/digital_subscriptions/doctype).
- **Core DocTypes**:
	- `File Version`: stores release metadata, file attachment, and `is_free` flag; computes SHA256 of the attached private file on save and names the record as `${Item.item_name} v{version}` in [digital_subscriptions/digital_subscriptions/doctype/file_version/file_version.py](digital_subscriptions/digital_subscriptions/doctype/file_version/file_version.py).
	- `File Subscription`: links `Customer` + `Item` + `Payment Entry` and drives access windows (`starts_on`/`ends_on`) in [digital_subscriptions/digital_subscriptions/doctype/file_subscription/file_subscription.py](digital_subscriptions/digital_subscriptions/doctype/file_subscription/file_subscription.py).
	- `File Settings`: single DocType with default availability days in [digital_subscriptions/digital_subscriptions/doctype/file_settings/file_settings.json](digital_subscriptions/digital_subscriptions/doctype/file_settings/file_settings.json).
- **Payment Entry hook**: `Payment Entry` `on_submit` creates a `File Subscription` if the payment references a single-item Sales Invoice/Order/Quotation/Delivery Note and a non-disabled `File Version` exists; see [digital_subscriptions/hooks.py](digital_subscriptions/hooks.py) and [digital_subscriptions/digital_subscriptions/doctype/file_subscription/file_subscription.py](digital_subscriptions/digital_subscriptions/doctype/file_subscription/file_subscription.py).
- **Download and update endpoints** (whitelisted):
	- `download()` requires a valid subscription for paid versions; free versions bypass subscription checks.
	- `xml()` emits Joomla update XML; supports paid `dlid` or free tokens of the form `FREE-<item_code>`; the same token is echoed in download URLs.
	- `phrs_download()` accepts `subscription` or `dlid` query args and rejects `FREE-` tokens for paid versions.
	All live in [digital_subscriptions/digital_subscriptions/doctype/file_version/file_version.py](digital_subscriptions/digital_subscriptions/doctype/file_version/file_version.py).
- **Access control**: Item Group website permission is always allowed via [digital_subscriptions/hooks/item_group.py](digital_subscriptions/hooks/item_group.py).
- **Portal user creation override**: this app monkey-patches ERPNext portal user setup to create and link Customer/Supplier Contacts with retry/backoff to avoid race conditions; see [digital_subscriptions/__init__.py](digital_subscriptions/__init__.py) and [digital_subscriptions/overrides.py](digital_subscriptions/overrides.py).
- **Migration helper**: `create_subscriptions()` backfills subscriptions from recent `Payment Entry` records (admin only) in [digital_subscriptions/digital_subscriptions/hooks/migrate.py](digital_subscriptions/digital_subscriptions/hooks/migrate.py).
- **Web form**: the `vies` web form updates `Customer.tax_id` for VAT validation; definition in [digital_subscriptions/digital_subscriptions/web_form/vies/vies.json](digital_subscriptions/digital_subscriptions/web_form/vies/vies.json).

If any of these sections are unclear or missing a workflow you rely on, tell me what to add or tighten.
