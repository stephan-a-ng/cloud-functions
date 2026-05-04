import base64
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from cloudevents.http import CloudEvent
from google.events.cloud import firestore as firestoredata
from google.protobuf.json_format import MessageToDict
import functions_framework

# Optional at import time so functions that don't use Slack (e.g. the
# email-pipeline function) can deploy without these env vars set.
# The Slack handlers check for the value before calling Slack.
SLACK_FUNDRAISING_WEBHOOK = os.environ.get("SLACK_FUNDRAISING_WEBHOOK", "")
SLACK_DEPLOYMENT_WEBHOOK = os.environ.get("SLACK_DEPLOYMENT_WEBHOOK", "")

# CRM intake — only required for the on_waitlist_submission_to_crm function.
# Read lazily inside that handler so the other Slack functions still deploy
# even if these are unset for a given environment.
CRM_API_URL = os.environ.get("CRM_API_URL", "")
CRM_API_URL_STAGING = os.environ.get("CRM_API_URL_STAGING", "")
INTAKE_SHARED_SECRET = os.environ.get("INTAKE_SHARED_SECRET", "")

# Pipeline-notification mailer. PIPELINE_SENDER is the Workspace user the
# Gmail API impersonates via domain-wide delegation; PIPELINE_RECIPIENT is
# where the email goes. Both default to the pipeline@ mailbox so the
# notification self-loops into one inbox.
PIPELINE_SENDER = os.environ.get("PIPELINE_SENDER", "accelerate@moonfive.tech")
PIPELINE_RECIPIENT = os.environ.get("PIPELINE_RECIPIENT", "pipeline@moonfive.tech")


def _parse_event(event: CloudEvent) -> dict:
    """Parse a Firestore CloudEvent into a plain dict of field values."""
    print(f"Event data type: {type(event.data)}")
    print(f"Event data (first 500 chars): {str(event.data)[:500]}")
    firestore_payload = firestoredata.DocumentEventData()
    firestore_payload._pb.MergeFromString(event.data)
    doc_dict = MessageToDict(firestore_payload._pb)
    print(f"Parsed doc_dict: {json.dumps(doc_dict, default=str)[:500]}")
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
    if not webhook_url:
        raise RuntimeError("Slack webhook URL is not configured for this function")
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


# ── Waitlist/Qualification → #deployment ────────────────────────────────────

@functions_framework.cloud_event
def on_waitlist_submission(event: CloudEvent):
    """Triggered when a new document is created in waitlist."""
    data = _parse_event(event)

    first = data.get("first_name", "")
    last = data.get("last_name", "")
    email = data.get("email", "N/A")
    phone = data.get("phone", "N/A")
    form_type = data.get("form_type", "waitlist")
    address = data.get("address", "N/A")
    residency_type = data.get("residency_type", "")
    ev_status = data.get("ev_status", "")
    parking_type = data.get("parking_type", "")
    timeline = data.get("timeline", "")

    if form_type == "reach-3.0":
        title = "New REACH 3.0 Lead"
    elif form_type == "qualification":
        title = "New Skip the Line Submission"
    else:
        title = "New Waitlist Signup"

    fields = [
        {"type": "mrkdwn", "text": f"*Name:*\n{first} {last}"},
        {"type": "mrkdwn", "text": f"*Email:*\n{email}"},
        {"type": "mrkdwn", "text": f"*Phone:*\n{phone}"},
        {"type": "mrkdwn", "text": f"*Address:*\n{address}"},
    ]
    if residency_type:
        fields.append({"type": "mrkdwn", "text": f"*Residency:*\n{residency_type}"})
    if ev_status:
        fields.append({"type": "mrkdwn", "text": f"*EV Status:*\n{ev_status}"})
    if parking_type:
        fields.append({"type": "mrkdwn", "text": f"*Parking:*\n{parking_type}"})
    if timeline:
        fields.append({"type": "mrkdwn", "text": f"*Timeline:*\n{timeline}"})
    if form_type == "reach-3.0":
        verdict = data.get("qualification_outcome") or ""
        unit_count = data.get("unit_count") or ""
        utility = data.get("utility_provider") or ""
        if verdict:
            fields.append({"type": "mrkdwn", "text": f"*Verdict:*\n{verdict}"})
        if unit_count:
            fields.append({"type": "mrkdwn", "text": f"*Units:*\n{unit_count}"})
        if utility:
            fields.append({"type": "mrkdwn", "text": f"*Utility:*\n{utility}"})

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title}},
        {"type": "section", "fields": fields},
    ]

    _post_to_slack(SLACK_DEPLOYMENT_WEBHOOK, blocks)


# ── Waitlist/Qualification → CRM ─────────────────────────────────────────────

def _forward_waitlist_to_crm(event: CloudEvent, *, crm_url: str, label: str):
    """Shared body for the prod and staging CRM-fanout functions.

    A non-2xx response raises so Cloud Functions retries; the CRM side
    is idempotent on firestore_doc_id, so retries can't dup-create.
    """
    if not crm_url or not INTAKE_SHARED_SECRET:
        raise RuntimeError(
            f"{label}: CRM URL and INTAKE_SHARED_SECRET must both be set"
        )

    data = _parse_event(event)

    # Pull the Firestore doc id from the CloudEvent subject. The subject
    # looks like 'documents/waitlist/{docId}' for native-mode triggers.
    subject = event.get("subject") or ""
    doc_id = subject.rsplit("/", 1)[-1] if subject else ""

    # Build the CRM payload - snake_case keys, matching WaitlistIntakePayload.
    payload = {
        "firestore_doc_id": doc_id,
        "submitted_at": data.get("submitted_at"),
        "form_type": data.get("form_type") or "waitlist",
        "first_name": data.get("first_name") or "",
        "last_name": data.get("last_name") or "",
        "email": data.get("email") or "",
        "phone": data.get("phone") or "",
        "sms_consent": data.get("sms_consent"),
        "address": data.get("address") or "",
        "unit": data.get("unit") or "",
        "lat": data.get("lat"),
        "lng": data.get("lng"),
        "residency_type": data.get("residency_type") or "",
        "residency_type_other": data.get("residency_type_other") or "",
        "building_size": data.get("building_size") or "",
        "owner_relationship": data.get("owner_relationship") or "",
        "timeline": data.get("timeline") or "",
        "ev_status": data.get("ev_status") or "",
        "parking_dedicated": data.get("parking_dedicated") or "",
        "parking_type": data.get("parking_type") or "",
        "parking_type_other": data.get("parking_type_other") or "",
        "newsletter": data.get("newsletter"),
        "for_myself": data.get("for_myself"),
        "comment": data.get("comment") or "",
        # REACH 3.0 attestations + verdict (only set when the user
        # came in through /reach-3.0). Empty defaults are safe; the
        # CRM intake schema treats them as optional.
        "unit_count": data.get("unit_count") or "",
        "tenancy": data.get("tenancy") or "",
        "utility_provider": data.get("utility_provider") or "",
        "dac_attest": data.get("dac_attest") or "",
        "qualification_outcome": data.get("qualification_outcome") or "",
        "ineligibility_reasons": data.get("ineligibility_reasons") or [],
        "existing_deal_id": data.get("existing_deal_id") or "",
    }

    if not payload["email"] or not payload["firestore_doc_id"]:
        print(f"{label}: skipping CRM forward — missing email or doc_id: {payload}")
        return

    url = crm_url.rstrip("/") + "/v1/intake/waitlist"
    resp = requests.post(
        url,
        json=payload,
        headers={"X-Intake-Secret": INTAKE_SHARED_SECRET},
        timeout=15,
    )
    print(f"{label}: CRM intake → {resp.status_code} doc={doc_id} email={payload['email']}")
    resp.raise_for_status()


@functions_framework.cloud_event
def on_waitlist_submission_to_crm(event: CloudEvent):
    """Forward a new waitlist Firestore doc to the production CRM."""
    _forward_waitlist_to_crm(event, crm_url=CRM_API_URL, label="prod")


@functions_framework.cloud_event
def on_waitlist_submission_to_crm_staging(event: CloudEvent):
    """Forward a new waitlist Firestore doc to the staging CRM.

    Runs in parallel with the prod fanout so staging always has a fresh
    shadow copy of real submissions for testing CRM changes against
    real data shapes.
    """
    _forward_waitlist_to_crm(event, crm_url=CRM_API_URL_STAGING, label="staging")


# ── Waitlist/Qualification → pipeline@moonfive.tech ─────────────────────────


def _get_mailer_sa_email() -> str:
    """Return the email of the Cloud Function's runtime service account."""
    resp = requests.get(
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email",
        headers={"Metadata-Flavor": "Google"},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.text.strip()


def _gmail_client():
    """Build a Gmail API client that sends as PIPELINE_SENDER.

    Uses keyless DWD: the runtime SA self-signs JWTs via the IAM
    Credentials API (`roles/iam.serviceAccountTokenCreator` granted on
    itself), so no JSON key file is needed.
    """
    from google.auth import default, iam
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    source_credentials, _ = default()
    sa_email = _get_mailer_sa_email()
    signer = iam.Signer(
        request=Request(),
        credentials=source_credentials,
        service_account_email=sa_email,
    )
    delegated = service_account.Credentials(
        signer=signer,
        service_account_email=sa_email,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.send"],
        subject=PIPELINE_SENDER,
    )
    return build("gmail", "v1", credentials=delegated, cache_discovery=False)


def _build_pipeline_email(data: dict) -> tuple[str, str, str]:
    """Return (subject, plain_text_body, html_body) for the pipeline email."""
    first = data.get("first_name", "") or ""
    last = data.get("last_name", "") or ""
    name = f"{first} {last}".strip() or "(no name)"
    email = data.get("email", "N/A")
    phone = data.get("phone", "") or "N/A"
    form_type = data.get("form_type", "waitlist")
    address = data.get("address", "") or ""
    unit = data.get("unit", "") or ""
    if address and unit:
        address = f"{address}, Unit {unit}"
    address = address or "N/A"
    residency = data.get("residency_type", "") or ""
    ev_status = data.get("ev_status", "") or ""
    parking_type = data.get("parking_type", "") or ""
    timeline = data.get("timeline", "") or ""
    comment = data.get("comment", "") or ""

    label = "Skip the Line Submission" if form_type == "qualification" else "Waitlist Signup"
    subject = f"New {label}: {name}"

    # Plain-text body — mirror the Slack fields, optional ones only when present.
    text_lines = [
        f"New {label.lower()} via moonfive.tech",
        "",
        f"Name:     {name}",
        f"Email:    {email}",
        f"Phone:    {phone}",
        f"Address:  {address}",
    ]
    if residency:
        text_lines.append(f"Role:     {residency}")
    if ev_status:
        text_lines.append(f"EV:       {ev_status}")
    if parking_type:
        text_lines.append(f"Parking:  {parking_type}")
    if timeline:
        text_lines.append(f"Timeline: {timeline}")
    if comment:
        text_lines.extend(["", "Comment:", comment])
    text_body = "\n".join(text_lines)

    # Minimal HTML version for clients that prefer it.
    rows = [
        ("Name", name),
        ("Email", email),
        ("Phone", phone),
        ("Address", address),
    ]
    if residency:
        rows.append(("Role", residency))
    if ev_status:
        rows.append(("EV", ev_status))
    if parking_type:
        rows.append(("Parking", parking_type))
    if timeline:
        rows.append(("Timeline", timeline))

    def _esc(s: str) -> str:
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    rows_html = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#666;'>{_esc(k)}</td>"
        f"<td style='padding:4px 0;'>{_esc(v)}</td></tr>"
        for k, v in rows
    )
    comment_html = (
        f"<p style='margin-top:16px;white-space:pre-wrap;'>{_esc(comment)}</p>"
        if comment
        else ""
    )
    html_body = (
        f"<div style='font-family:system-ui,sans-serif;font-size:14px;color:#222;'>"
        f"<h2 style='margin:0 0 12px 0;'>New {_esc(label)}</h2>"
        f"<table>{rows_html}</table>"
        f"{comment_html}"
        f"</div>"
    )
    return subject, text_body, html_body


@functions_framework.cloud_event
def on_waitlist_submission_to_email(event: CloudEvent):
    """Send a pipeline notification email when a new waitlist doc lands.

    Sends as PIPELINE_SENDER (default pipeline@moonfive.tech) via Gmail
    API + domain-wide delegation. Mirrors the Slack notification format.
    """
    data = _parse_event(event)
    if not data.get("email"):
        print("pipeline-mailer: skipping — submission has no email address")
        return

    subject, text_body, html_body = _build_pipeline_email(data)

    msg = MIMEMultipart("alternative")
    msg["From"] = PIPELINE_SENDER
    msg["To"] = PIPELINE_RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    gmail = _gmail_client()
    sent = gmail.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(
        f"pipeline-mailer: sent message id={sent.get('id')} "
        f"form={data.get('form_type')} email={data.get('email')}"
    )
