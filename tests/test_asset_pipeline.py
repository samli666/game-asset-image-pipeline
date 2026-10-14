import asyncio
import base64

from game_asset_pipeline.asset_pipeline import AssetPipeline
from game_asset_pipeline.models import AssetKind, AssetState, AssetUploadRequest, ModerationQueue


class RecordingInfrai:
    def __init__(self) -> None:
        self.resize_calls: list[dict[str, object]] = []

    async def upload_image(self, **kwargs: object) -> dict[str, object]:
        return {"url": "https://media.example/player-source.png"}

    async def resize_image(self, **kwargs: object) -> dict[str, object]:
        self.resize_calls.append(kwargs)
        return {"url": "https://media.example/event-banner.webp", "stored": True}


def test_event_banner_is_cropped_and_sent_to_live_event_review() -> None:
    asyncio.run(check_event_banner_decision())


async def check_event_banner_decision() -> None:
    gateway = RecordingInfrai()
    pipeline = AssetPipeline(gateway)  # type: ignore[arg-type]
    request = AssetUploadRequest(
        asset_id="asset-evt-42",
        player_id="player-7",
        kind=AssetKind.EVENT_BANNER,
        filename="launch-night.png",
        content_type="image/png",
        data_base64=base64.b64encode(b"image bytes").decode("ascii"),
    )

    result = await pipeline.process(request)

    assert gateway.resize_calls == [
        {
            "image": "https://media.example/player-source.png",
            "width": 1600,
            "height": 900,
            "fit": "cover",
            "asset_id": "asset-evt-42",
        }
    ]
    assert result.state is AssetState.QUEUED_FOR_REVIEW
    assert result.moderation_queue is ModerationQueue.LIVE_EVENT
    assert pipeline.moderation_items[0].asset_id == "asset-evt-42"
    assert pipeline.events[0].event_type == "asset.processed"
