import json
import os

import requests
from cloudevents.http import CloudEvent
from google.events.cloud import firestore as firestoredata
from google.protobuf.json_format import MessageToDict
import functions_framework

SLACK_FUNDRAISING_WEBHOOK = os.environ["SLACK_FUNDRAISING_WEBHOOK"]
SLACK_DEPLOYMENT_WEBHOOK = os.environ["SLACK_DEPLOYMENT_WEBHOOK"]


def _parse_event(event: CloudEvent) -> dict:
    """Parse a Firestore CloudEvent into a plain dict of field values."""
    firestore_payload = firestoredata.DocumentEventData()
    firestore_payload._pb.MergeFromString(event.data)
    doc_dict = MessageToDict(firestore_payload._pb)
    fields = doc_dict.get("value", {}).get("fields", {})
    return _flatten_fields(fields)


def _flatten_fields(fields: dict) -> dict:
    """Convert Firestore REST-style typed fields to plain values."""
    result = {}
    for key, val in fields.items():
        if "stringValue" in val:
            result[key] = val["stringValue"]
        elif "integerValue" in val:
            result[key] = int(val["integerValue"])
        elif "doubleValue" in val:
            result[key] = val["doubleValue"]
        elif "booleanValue" in val:
            result[key] = val["booleanValue"]
        elif "timestampValue" in val:
            result[key] = val["timestampValue"]
        elif "nullValue" in val:
            result[key] = None
        elif "mapValue" in val:
            result[key] = _flatten_fields(val["mapValue"].get("fields", {}))
        elif "arrayValue" in val:
            result[key] = [
                _flatten_fields({"_": v}).get("_") for v in val["arrayValue"].get("values", [])
            ]
        else:
            result[key] = str(val)
    return result


def _post_to_slack(webhook_url, blocks):
    """Send a message to a Slack channel via webhook."""
    resp = requests.post(webhook_url, json={"blocks": blocks}, timeout=10)
    resp.raise_for_status()


# ── Investor Leads → #fundraising ────────────────────────────────────────────

@functions_framework.cloud_event
def on_investor_lead(event: CloudEvent):
    """Triggered when a new document is created in investor_leads."""
    data = _parse_event(event)

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
            "text": {"type": "plain_text", "text": "New Investor Lead"},
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
    data = _parse_event(event)

    name = data.get("name", "N/A")
    email = data.get("email", "N/A")
    phone = data.get("phone", "N/A")
    auth = data.get("auth_provider", "N/A")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "New Customer Signup"},
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
    data = _parse_event(event)

    name = data.get("name", "N/A")
    email = data.get("email", "N/A")
    message = data.get("message", "")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "New Contact Submission"},
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
