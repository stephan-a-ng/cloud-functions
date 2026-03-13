#!/bin/bash
set -euo pipefail

PROJECT="ascendant-nova-487001-d2"
REGION="us-central1"
DATABASE="(default)"

# Load webhook URLs from .env file
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

: "${SLACK_FUNDRAISING_WEBHOOK:?Set SLACK_FUNDRAISING_WEBHOOK in .env}"
: "${SLACK_DEPLOYMENT_WEBHOOK:?Set SLACK_DEPLOYMENT_WEBHOOK in .env}"

ENV_VARS="SLACK_FUNDRAISING_WEBHOOK=${SLACK_FUNDRAISING_WEBHOOK},SLACK_DEPLOYMENT_WEBHOOK=${SLACK_DEPLOYMENT_WEBHOOK}"

echo "=== Deploying investor_leads → #fundraising ==="
gcloud functions deploy on-investor-lead \
  --project="$PROJECT" \
  --region="$REGION" \
  --runtime=python312 \
  --entry-point=on_investor_lead \
  --source=. \
  --gen2 \
  --set-env-vars="$ENV_VARS" \
  --trigger-event-filters="type=google.cloud.firestore.document.v1.created" \
  --trigger-event-filters="database=$DATABASE" \
  --trigger-event-filters-path-pattern="document=investor_leads/{docId}" \
  --retry \
  --quiet

echo ""
echo "=== Deploying customers → #deployment ==="
gcloud functions deploy on-customer \
  --project="$PROJECT" \
  --region="$REGION" \
  --runtime=python312 \
  --entry-point=on_customer \
  --source=. \
  --gen2 \
  --set-env-vars="$ENV_VARS" \
  --trigger-event-filters="type=google.cloud.firestore.document.v1.created" \
  --trigger-event-filters="database=$DATABASE" \
  --trigger-event-filters-path-pattern="document=customers/{docId}" \
  --retry \
  --quiet

echo ""
echo "=== Deploying contact_submissions → #deployment ==="
gcloud functions deploy on-contact-submission \
  --project="$PROJECT" \
  --region="$REGION" \
  --runtime=python312 \
  --entry-point=on_contact_submission \
  --source=. \
  --gen2 \
  --set-env-vars="$ENV_VARS" \
  --trigger-event-filters="type=google.cloud.firestore.document.v1.created" \
  --trigger-event-filters="database=$DATABASE" \
  --trigger-event-filters-path-pattern="document=contact_submissions/{docId}" \
  --retry \
  --quiet

echo ""
echo "All 3 Cloud Functions deployed successfully!"
