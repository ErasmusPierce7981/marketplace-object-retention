from types import SimpleNamespace
from typing import Any

from marketplace_retention.migration import migrate_from_s3_lifecycle
from marketplace_retention.models import MarketplaceObject, MigrationRequest
from marketplace_retention.policy import retention_for


class RecordingInfrai:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.storage = SimpleNamespace(
            bucket=SimpleNamespace(
                create=self.create_bucket,
                set_lifecycle=self.set_lifecycle,
            )
        )
        self.cron = SimpleNamespace(create=self.create_cron)

    def create_bucket(self, **body: Any) -> dict[str, Any]:
        self.calls.append(("bucket", body))
        return {"name": body["name"]}

    def set_lifecycle(self, bucket: str, **body: Any) -> dict[str, Any]:
        self.calls.append(("lifecycle", {"bucket": bucket, **body}))
        return {"name": bucket}

    def create_cron(self, **body: Any) -> dict[str, Any]:
        self.calls.append(("cron", body))
        return {"job_id": "job-marketplace-sweep"}


def test_order_handoff_gets_longer_retention_than_conversation_updates() -> None:
    buyer = retention_for(
        MarketplaceObject(
            marketplace_id="market-7",
            order_id="order-42",
            filename="buyer-note.json",
            role="buyer_update",
        )
    )
    handoff = retention_for(
        MarketplaceObject(
            marketplace_id="market-7",
            order_id="order-42",
            filename="master.mov",
            role="order_handoff",
        )
    )

    assert buyer.key == "buyer-updates/market-7/order-42/buyer-note.json"
    assert buyer.expire_days == 7
    assert handoff.key == "order-handoffs/market-7/order-42/master.mov"
    assert handoff.expire_days == 30


def test_migration_creates_bucket_before_policy_and_shared_key_cron() -> None:
    client = RecordingInfrai()
    result = migrate_from_s3_lifecycle(
        MigrationRequest(
            bucket="marketplace-throwaway-media",
            sweep_url=(
                "https://marketplace.example.com/internal/object-sweep/"
                "marketplace-throwaway-media"
            ),
        ),
        client,
    )

    assert [name for name, _ in client.calls] == ["bucket", "lifecycle", "cron"]
    assert client.calls[1][1]["rules"] == [
        {"prefix": "seller-assets/", "expire_days": 2},
        {"prefix": "buyer-updates/", "expire_days": 7},
        {"prefix": "order-handoffs/", "expire_days": 30},
    ]
    assert client.calls[2][1]["task"].endswith(
        "/internal/object-sweep/marketplace-throwaway-media"
    )
    assert result.sweep_job_id == "job-marketplace-sweep"
