from pathlib import PurePosixPath

from .models import MarketplaceObject, ObjectRole, RetentionDecision


RETENTION_DAYS = {
    ObjectRole.SELLER_ASSET: 2,
    ObjectRole.BUYER_UPDATE: 7,
    ObjectRole.ORDER_HANDOFF: 30,
}

PREFIXES = {
    ObjectRole.SELLER_ASSET: "seller-assets/",
    ObjectRole.BUYER_UPDATE: "buyer-updates/",
    ObjectRole.ORDER_HANDOFF: "order-handoffs/",
}


def retention_for(item: MarketplaceObject) -> RetentionDecision:
    """Place one object in the lifecycle lane owned by its marketplace role."""
    filename = PurePosixPath(item.filename).name
    if filename in {"", ".", ".."}:
        raise ValueError("filename must identify an object")
    prefix = PREFIXES[item.role]
    key = f"{prefix}{item.marketplace_id}/{item.order_id}/{filename}"
    return RetentionDecision(key=key, expire_days=RETENTION_DAYS[item.role])


def lifecycle_rules() -> list[dict[str, object]]:
    return [
        {"prefix": PREFIXES[role], "expire_days": RETENTION_DAYS[role]}
        for role in ObjectRole
    ]

