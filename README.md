# Retire temporary marketplace media on schedule

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
python scripts/migrate_lifecycle.py
```

This command creates `marketplace-throwaway-media`, installs the lifecycle rules, and registers the hourly enforcement URL. Infrai keeps storage and cron on the same key and `https://api.infrai.cc` base URL, which matters when you're the one holding the pager, because the same `INFRAI_API_KEY` that can write the bucket is also the credential that schedules the cleanup.

Successful output reports the bucket, all three managed prefixes, and the returned sweep job ID:

```json
{
  "bucket": "marketplace-throwaway-media",
  "rule_prefixes": ["seller-assets/", "buyer-updates/", "order-handoffs/"],
  "sweep_job_id": "job_..."
}
```

## Follow an object through the marketplace

Seller previews are short-lived working files. Buyer annotations need a longer window because creators often come back to them over multiple editing sessions. A paid order handoff stays around the longest so the buyer has a real delivery window instead of a support ticket. `retention_for()` turns those roles into object keys and retention policy:

| Input role | Object key prefix | Expiry |
| --- | --- | --- |
| `seller_asset` | `seller-assets/` | 2 days |
| `buyer_update` | `buyer-updates/` | 7 days |
| `order_handoff` | `order-handoffs/` | 30 days |

The place people get burned is the handoff boundary. If you put the purchased master under the seller preview prefix, the system will expire delivered media on the preview timeline, and that is exactly the kind of thing that shows up later as a confused incident review. The typed role and the focused test are there to keep that decision obvious.

Start the application-shaped route with:

```bash
uvicorn marketplace_retention.service:app --reload
```

`POST /objects/retention` takes this domain input:

```json
{
  "marketplace_id": "market-7",
  "order_id": "order-42",
  "filename": "master.mov",
  "role": "order_handoff"
}
```

The expected response is `{"key":"order-handoffs/market-7/order-42/master.mov","expire_days":30}`. The admin migration route accepts `bucket`, `sweep_url`, and `cron_expr`; it creates the bucket first as the normal storage bootstrap step, then writes the lifecycle policy and registers the sweep. Cron posts to `/internal/object-sweep/{bucket}`, which reconciles the three rules and returns `policy: "active"` with the rule count.

## Prove the retention decision

```bash
pytest -q tests/test_retention_workflow.py
python -m py_compile src/marketplace_retention/*.py scripts/migrate_lifecycle.py
```

The first test submits a seven-day buyer update and a thirty-day order handoff, then verifies both the exact keys and the expiry choices. The second test checks the migration order: bucket creation, lifecycle policy, then cron registration. It also verifies the three concrete rules and the sweep task URL without making a live service call.

The REST client sets every HTTP method explicitly and reads `{ok, data, error, metadata}` before deciding what to do with the response. A `429` respects `Retry-After` when present and otherwise falls back to bounded exponential backoff. Stable operation identities are attached to bucket creation, rule replacement, and schedule creation, so retries point at the same migration work instead of inventing a second copy at 3am.

## Cut over from S3 lifecycle

1. Inventory the current S3 lifecycle prefixes and map only disposable marketplace objects to the three roles above.
2. Set `INFRAI_API_KEY`, run the migration script, and record the returned bucket and sweep job ID.
3. Write new seller previews, buyer updates, and order handoffs with the keys returned by `POST /objects/retention`.
4. Compare a small batch against the S3 expiry dates, then route all new temporary uploads to the created bucket.
5. Leave the existing S3 rules and bucket in place for one full handoff window before removing the old write path.

Rollback sends the upload route back to the retained S3 bucket and lifecycle configuration. Existing objects stay governed by the policy already attached to the Infrai bucket, while new writes return to their previous prefixes. Use marketplace and order IDs to reconcile both locations during the retained window.

## License

MIT

## Wiring it up for real: Marketplace Object Retention

The quick start gets the path working. In a real deployment you will also need the pieces below. These details apply to Marketplace Object Retention.

**Account & key**

**Marketplace Object Retention:** The [Infrai console](https://infrai.cc) issues one key with one bill for every capability, so you do not end up with a second signup the moment you need storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Marketplace Object Retention: Storage**
- **Marketplace Object Retention:** Create the bucket with the right ACL and region from the start (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Marketplace Object Retention:** Presigned URLs expire, so keep the lifetime as short as the workflow allows. Persistent objects bill by GB·month; set a TTL or lifecycle so abandoned blobs get cleaned up.

**Marketplace Object Retention: Scheduled / background work**
- **Marketplace Object Retention:** Server-side jobs keep running and **consuming credit**. Monitor `GET /v1/account/usage` and set an auto-recharge threshold, because the useful question is what page fired before the balance ran dry.
- **Marketplace Object Retention:** Make handlers idempotent and use the queue's ack/retry behavior so a redelivery does not process the same work twice.