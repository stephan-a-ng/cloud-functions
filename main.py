import os

import requests
from cloudevents.http import CloudEvent
import functions_framework

SLACK_FUNDRAISING_WEBHOOK = os.environ["SLACK_FUNDRAISING_WEBHOOK"]
SLACK_DEPLOYMENT_WEBHOOK = os.environ["SLACK_DEPLOYMENT_WEBHOOK"]


def _get_field_value(field):
    """Extract the value from a Firestore document field."""
    for type_key in ("stringValue", "integerValue", "doubleValue", "booleanValue", "timestampValue"):
        if type_key in field:
            return field[type_key]
    if "mapValue" in field:
        return {k: _get_field_value(v) for k, v in field["mapValue"].get("fields", {}).items()}
    if "arrayValue" in field:
        return [_get_field_value(v) for v in field["arrayValue"].get("values", [])]
    if "nullValue" in field:
        return None
    return str(field)


def _parse_fields(raw_fields):
    """Parse Firestore raw fields into a plain dict."""
    return {k: _get_field_value(v) for k, v in raw_fields.items()}


def _post_to_slack(webhook_url, blocks):
    """Send a message to a Slack channel via webhook."""
    resp = requests.post(webhook_url, json={"blocks": blocks}, timeout=10)
    resp.raise_for_status()


# ── Investor Leads → #fundraising ────────────────────────────────────────────

@functions_framework.cloud_event
def on_investor_lead(event: CloudEvent):
    """Triggered when a new document is created in investor_leads."""
    raw_fields = event.data["value"].get("fields", {})
    data = _parse_fields(raw_fields)

    first = data.get("first_name", "")
    last = data.get("last_name", "")
    email = data.get("email", "N/A")
    phone = data.get("phone", "N/A")
    investment_range = data.get("investment_range", "N/A")
    accredited = data.get("accredited_criteria", "N/A")
    message = data.get("message", "")
    source = data.get("source", "N/A")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🚀 New Investor Lead"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Name:*\n{first} {last}"},
                {"type": "mrkdwn", "text": f"*Email:*\n{email}"},
                {"type": "mrkdwn", "text": f"*Phone:*\n{phone}"},
                {"type": "mrkdwn", "text": f"*Investment Range:*\n{investment_range}"},
                {"type": "mrkdwn", "text": f"*Accredited Criteria:*\n{accredited}"},
                {"type": "mrkdwn", "text": f"*Source:*\n{source}"},
            ],
        },
    ]

    if message:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Message:*\n{message}"},
        })

    _post_to_slack(SLACK_FUNDRAISING_WEBHOOK, blocks)


# ── Customers → #deployment ──────────────────────────────────────────────────

@functions_framework.cloud_event
def on_customer(event: CloudEvent):
    """Triggered when a new document is created in customers."""
    raw_fields = event.data["value"].get("fields", {})
    data = _parse_fields(raw_fields)

    name = data.get("name", "N/A")
    email = data.get("email", "N/A")
    phone = data.get("phone", "N/A")
    auth = data.get("auth_provider", "N/A")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "👤 New Customer Signup"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Name:*\n{name}"},
                {"type": "mrkdwn", "text": f"*Email:*\n{email}"},
                {"type": "mrkdwn", "text": f"*Phone:*\n{phone}"},
                {"type": "mrkdwn", "text": f"*Auth Provider:*\n{auth}"},
            ],
        },
    ]

    _post_to_slack(SLACK_DEPLOYMENT_WEBHOOK, blocks)


# ── Contact Submissions → #deployment ────────────────────────────────────────

@functions_framework.cloud_event
def on_contact_submission(event: CloudEvent):
    """Triggered when a new document is created in contact_submissions."""
    raw_fields = event.data["value"].get("fields", {})
    data = _parse_fields(raw_fields)

    name = data.get("name", "N/A")
    email = data.get("email", "N/A")
    message = data.get("message", "")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📩 New Contact Submission"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Name:*\n{name}"},
                {"type": "mrkdwn", "text": f"*Email:*\n{email}"},
            ],
        },
    ]

    if message:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Message:*\n{message}"},
        })

    _post_to_slack(SLACK_DEPLOYMENT_WEBHOOK, blocks)
