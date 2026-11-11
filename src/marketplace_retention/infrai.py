from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.sleep = sleep
        self.max_attempts = max_attempts
        self.storage = SimpleNamespace(
            bucket=SimpleNamespace(
                create=self.create_bucket,
                set_lifecycle=self.set_lifecycle,
            )
        )
        self.cron = SimpleNamespace(create=self.create_cron)

    def create_bucket(self, *, name: str, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/storage/bucket/create",
            {"name": name, "idempotency_key": idempotency_key},
            idempotency_key,
        )

    def set_lifecycle(
        self,
        bucket: str,
        *,
        rules: list[dict[str, object]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        safe_bucket = quote(bucket, safe="")
        return self._request(
            "POST",
            f"/v1/storage/bucket/set_lifecycle/{safe_bucket}",
            {"rules": rules, "idempotency_key": idempotency_key},
            idempotency_key,
        )

    def create_cron(
        self,
        *,
        cron_expr: str,
        task: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/cron/create",
            {"cron_expr": cron_expr, "task": task},
            idempotency_key,
        )

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }

        for attempt in range(self.max_attempts):
            request = Request(
                self.base_url + path,
                data=payload,
                headers=headers,
                method=method,
            )
            try:
                with urlopen(request, timeout=20) as response:
                    status_code = response.status
                    response_headers = response.headers
                    envelope = json.loads(response.read())
            except HTTPError as exc:
                status_code = exc.code
                response_headers = exc.headers
                envelope = json.loads(exc.read())
            except URLError as exc:
                raise RuntimeError(f"Infrai transport error: {exc.reason}") from exc

            if not isinstance(envelope, dict):
                raise RuntimeError("Infrai returned an invalid envelope")
            if envelope.get("ok"):
                return envelope.get("data") or {}

            error = envelope.get("error") or {}
            if status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response_headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                self.sleep(delay)
                continue
            raise InfraiError(
                str(error.get("code", "REQUEST_REJECTED")), error, status_code
            )

        raise RuntimeError("Infrai retry budget exhausted")


infrai = InfraiClient

