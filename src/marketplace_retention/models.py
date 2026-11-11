from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class ObjectRole(str, Enum):
    SELLER_ASSET = "seller_asset"
    BUYER_UPDATE = "buyer_update"
    ORDER_HANDOFF = "order_handoff"


class MarketplaceObject(BaseModel):
    marketplace_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    role: ObjectRole


class RetentionDecision(BaseModel):
    key: str
    expire_days: int


class MigrationRequest(BaseModel):
    bucket: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9-]+[a-z0-9]$")
    sweep_url: HttpUrl
    cron_expr: str = Field(default="17 * * * *", min_length=1)


class MigrationResult(BaseModel):
    bucket: str
    rule_prefixes: list[str]
    sweep_job_id: str

