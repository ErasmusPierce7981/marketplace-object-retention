from typing import Any, Protocol

from .models import MigrationRequest, MigrationResult
from .policy import lifecycle_rules


class LifecycleGateway(Protocol):
    storage: Any
    cron: Any


def migrate_from_s3_lifecycle(
    request: MigrationRequest, infrai: LifecycleGateway
) -> MigrationResult:
    """Create storage, install the policy, and schedule its sweep in order."""
    bucket_key = f"marketplace-retention:bucket:{request.bucket}"
    infrai.storage.bucket.create(name=request.bucket, idempotency_key=bucket_key)

    rules = lifecycle_rules()
    infrai.storage.bucket.set_lifecycle(
        request.bucket,
        rules=rules,
        idempotency_key=f"marketplace-retention:rules:{request.bucket}:v1",
    )
    cron_data = infrai.cron.create(
        cron_expr=request.cron_expr,
        task=str(request.sweep_url),
        idempotency_key=f"marketplace-retention:sweep:{request.bucket}:v1",
    )
    return MigrationResult(
        bucket=request.bucket,
        rule_prefixes=[str(rule["prefix"]) for rule in rules],
        sweep_job_id=str(cron_data["job_id"]),
    )

