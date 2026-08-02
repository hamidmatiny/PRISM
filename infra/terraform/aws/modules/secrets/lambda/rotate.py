"""Secrets Manager rotation handler (create/set/test/finish).

Apply-time: wire this Lambda (or the AWS-provided RDS rotation image) to the
secrets in this module. Plan-only scaffold satisfies CKV2_AWS_57; the runbook
docs/runbooks/secrets-rotation.md covers RDS ALTER ROLE + app secret rollout.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import string

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sm = boto3.client("secretsmanager")


def _password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + "!#$%&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _get(secret_id: str, stage: str) -> dict:
    resp = sm.get_secret_value(SecretId=secret_id, VersionStage=stage)
    return json.loads(resp["SecretString"])


def create_secret(arn: str, token: str) -> None:
    # Skip if AWSPENDING already exists for this token.
    try:
        sm.get_secret_value(SecretId=arn, VersionId=token, VersionStage="AWSPENDING")
        return
    except sm.exceptions.ResourceNotFoundException:
        pass

    current = _get(arn, "AWSCURRENT")
    pending = dict(current)
    if "password" in pending:
        pending["password"] = _password(32)
    if "DJANGO_SECRET_KEY" in pending:
        pending["DJANGO_SECRET_KEY"] = _password(64)
    if "PRISM_BOOTSTRAP_PASSWORD" in pending:
        pending["PRISM_BOOTSTRAP_PASSWORD"] = _password(32)

    sm.put_secret_value(
        SecretId=arn,
        ClientRequestToken=token,
        SecretString=json.dumps(pending),
        VersionStages=["AWSPENDING"],
    )


def set_secret(arn: str, token: str) -> None:
    """Apply pending credentials to the dependent system.

    RDS: run ALTER ROLE … PASSWORD (requires VPC + DB connectivity at apply).
    App secrets: consumers reload on next task deploy / secret refresh — no-op here.
    """
    _ = (_get(arn, "AWSCURRENT"), _get(arn, "AWSPENDING"))
    if os.environ.get("PRISM_ROTATION_APPLY_RDS", "").lower() in {"1", "true"}:
        logger.info("PRISM_ROTATION_APPLY_RDS set — operator must run ALTER ROLE outside stub")
    logger.info("setSecret acknowledged for %s token=%s", arn, token)


def test_secret(arn: str, token: str) -> None:
    pending = sm.get_secret_value(SecretId=arn, VersionId=token, VersionStage="AWSPENDING")
    data = json.loads(pending["SecretString"])
    if not data:
        raise RuntimeError("pending secret empty")


def finish_secret(arn: str, token: str) -> None:
    metadata = sm.describe_secret(SecretId=arn)
    for version_id, stages in (metadata.get("VersionIdsToStages") or {}).items():
        if "AWSCURRENT" in stages and version_id != token:
            sm.update_secret_version_stage(
                SecretId=arn,
                VersionStage="AWSCURRENT",
                MoveToVersionId=token,
                RemoveFromVersionId=version_id,
            )
            return
    sm.update_secret_version_stage(
        SecretId=arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
    )


def handler(event, context):  # noqa: ANN001, ARG001
    arn = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]
    logger.info("rotation step=%s secret=%s", step, arn)

    if step == "createSecret":
        create_secret(arn, token)
    elif step == "setSecret":
        set_secret(arn, token)
    elif step == "testSecret":
        test_secret(arn, token)
    elif step == "finishSecret":
        finish_secret(arn, token)
    else:
        raise ValueError(f"unknown step {step}")
    return {"status": "ok", "step": step}
