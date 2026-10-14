import asyncio
import base64
import json

import httpx

from game_asset_pipeline.infrai_client import InfraiClient


def test_upload_image_sends_json() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["content-type"] == "application/json"
        assert json.loads(request.content) == {
            "file": base64.b64encode(b"image bytes").decode("ascii"),
            "filename": "avatar.png",
        }
        return httpx.Response(200, json={"ok": True, "data": {"url": "https://example.test/avatar.png"}})

    async def check() -> None:
        client = InfraiClient(api_key="test", transport=httpx.MockTransport(handler))
        try:
            await client.upload_image(
                filename="avatar.png",
                content_type="image/png",
                content=b"image bytes",
                asset_id="asset-1",
            )
        finally:
            await client.close()

    asyncio.run(check())
