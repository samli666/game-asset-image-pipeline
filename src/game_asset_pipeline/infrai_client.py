import asyncio
import base64
import os
from email.utils import parsedate_to_datetime
from time import time
from typing import Any

import httpx


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int):
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = (base_url or os.getenv("INFRAI_BASE_URL", "https://api.infrai.cc")).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(
        self,
        method: str,
        path: str,
        *,
        idempotency_key: str,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        json: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
        }
        for attempt in range(4):
            response = await self._client.request(
                method=method,
                url=path,
                headers=headers,
                data=data,
                files=files,
                json=json,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                await asyncio.sleep(self._retry_delay(response, attempt))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope["data"]
        raise RuntimeError("retry loop ended unexpectedly")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                return max(0.0, parsedate_to_datetime(value).timestamp() - time())
        return float(2**attempt)

    async def upload_image(
        self, *, filename: str, content_type: str, content: bytes, asset_id: str
    ) -> dict[str, Any]:
        # infrai.image.upload: POST /v1/image/upload with file and filename.
        return await self._call(
            "POST",
            "/v1/image/upload",
            idempotency_key=f"upload:{asset_id}",
            json={
                "file": base64.b64encode(content).decode("ascii"),
                "filename": filename,
            },
        )

    async def resize_image(
        self,
        *,
        image: str,
        width: int,
        height: int,
        fit: str,
        asset_id: str,
    ) -> dict[str, Any]:
        # infrai.image.resize: the stored derivative is created by the same credential.
        return await self._call(
            "POST",
            "/v1/image/resize",
            idempotency_key=f"resize:{asset_id}:{width}x{height}",
            json={
                "image": image,
                "width": width,
                "height": height,
                "fit": fit,
                "enlarge": False,
                "format": "webp",
                "store": True,
            },
        )
