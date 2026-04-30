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
: "${CRM_API_URL:?Set CRM_API_URL in .env (production CRM URL)}"
: "${CRM_API_URL_STAGING:?Set CRM_API_URL_STAGING in .env (staging CRM URL)}"
: "${INTAKE_SHARED_SECRET:?Set INTAKE_SHARED_SECRET in .env (32-byte token, must match CRM env)}"

ENV_VARS="SLACK_FUNDRAISING_WEBHOOK=${SLACK_FUNDRAISING_WEBHOOK},SLACK_DEPLOYMENT_WEBHOOK=${SLACK_DEPLOYMENT_WEBHOOK}"
CRM_ENV_VARS="CRM_API_URL=${CRM_API_URL},CRM_API_URL_STAGING=${CRM_API_URL_STAGING},INTAKE_SHARED_SECRET=${INTAKE_SHARED_SECRET}"

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
echo "=== Deploying waitlist → #deployment ==="
gcloud functions deploy on-waitlist-submission \
  --project="$PROJECT" \
  --region="$REGION" \
  --runtime=python312 \
  --entry-point=on_waitlist_submission \
  --source=. \
  --gen2 \
  --set-env-vars="$ENV_VARS" \
  --trigger-event-filters="type=google.cloud.firestore.document.v1.created" \
  --trigger-event-filters="database=$DATABASE" \
  --trigger-event-filters-path-pattern="document=waitlist/{docId}" \
  --retry \
  --quiet

echo ""
echo "=== Deploying waitlist → CRM (production) ==="
gcloud functions deploy on-waitlist-submission-to-crm \
  --project="$PROJECT" \
  --region="$REGION" \
  --runtime=python312 \
  --entry-point=on_waitlist_submission_to_crm \
  --source=. \
  --gen2 \
  --set-env-vars="$ENV_VARS,$CRM_ENV_VARS" \
  --trigger-event-filters="type=google.cloud.firestore.document.v1.created" \
  --trigger-event-filters="database=$DATABASE" \
  --trigger-event-filters-path-pattern="document=waitlist/{docId}" \
  --retry \
  --quiet

echo ""
echo "=== Deploying waitlist → CRM (staging) ==="
gcloud functions deploy on-waitlist-submission-to-crm-staging \
  --project="$PROJECT" \
  --region="$REGION" \
  --runtime=python312 \
  --entry-point=on_waitlist_submission_to_crm_staging \
  --source=. \
  --gen2 \
  --set-env-vars="$ENV_VARS,$CRM_ENV_VARS" \
  --trigger-event-filters="type=google.cloud.firestore.document.v1.created" \
  --trigger-event-filters="database=$DATABASE" \
  --trigger-event-filters-path-pattern="document=waitlist/{docId}" \
  --retry \
  --quiet

echo ""
echo "=== Deploying waitlist → pipeline@ email ==="
gcloud functions deploy on-waitlist-submission-to-email \
  --project="$PROJECT" \
  --region="$REGION" \
  --runtime=python312 \
  --entry-point=on_waitlist_submission_to_email \
  --service-account="cf-pipeline-mailer@${PROJECT}.iam.gserviceaccount.com" \
  --source=. \
  --gen2 \
  --set-env-vars="PIPELINE_SENDER=pipeline@moonfive.tech,PIPELINE_RECIPIENT=pipeline@moonfive.tech" \
  --trigger-event-filters="type=google.cloud.firestore.document.v1.created" \
  --trigger-event-filters="database=$DATABASE" \
  --trigger-event-filters-path-pattern="document=waitlist/{docId}" \
  --retry \
  --quiet

echo ""
echo "All 7 Cloud Functions deployed successfully!"
