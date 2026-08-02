#!/bin/sh
set -eu
mkdir -p "${PRISM_DATA_ROOT:-/data}/control-plane" \
  "${PRISM_CV_REVIEW_PENDING_DIR:-/data/cv-review-queue/pending}" \
  "${PRISM_CV_REVIEW_DECIDED_DIR:-/data/cv-review-queue/decided}" \
  "${PRISM_CV_FINDINGS_GOLD_DIR:-/data/cv-findings/gold}"

python manage.py migrate --noinput
python manage.py bootstrap_rbac
exec "$@"
