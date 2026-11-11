from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from .infrai import InfraiClient, InfraiError
from .migration import migrate_from_s3_lifecycle
from .models import MarketplaceObject, MigrationRequest, MigrationResult, RetentionDecision
from .policy import lifecycle_rules, retention_for


app = FastAPI(title="Marketplace object retention")


def gateway() -> InfraiClient:
    return InfraiClient()


Gateway = Annotated[InfraiClient, Depends(gateway)]


@app.post("/objects/retention", response_model=RetentionDecision)
def decide_retention(item: MarketplaceObject) -> RetentionDecision:
    return retention_for(item)


@app.post("/admin/migrations/s3-lifecycle", response_model=MigrationResult)
def run_migration(request: MigrationRequest, infrai: Gateway) -> MigrationResult:
    try:
        return migrate_from_s3_lifecycle(request, infrai)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=exc.detail) from exc


@app.post("/internal/object-sweep/{bucket}")
def enforce_lifecycle(bucket: str, infrai: Gateway) -> dict[str, object]:
    """Reconcile the bucket policy when the scheduled sweep arrives."""
    try:
        rules = lifecycle_rules()
        infrai.storage.bucket.set_lifecycle(
            bucket,
            rules=rules,
            idempotency_key=f"marketplace-retention:sweep:{bucket}:v1",
        )
        return {"bucket": bucket, "policy": "active", "rule_count": len(rules)}
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=exc.detail) from exc
