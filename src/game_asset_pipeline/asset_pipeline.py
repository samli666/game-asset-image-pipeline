import base64
import binascii
from dataclasses import dataclass
from typing import Any, Protocol

from .models import (
    AssetKind,
    AssetProcessedEvent,
    AssetState,
    AssetUploadRequest,
    AssetUploadResult,
    ModerationItem,
    ModerationQueue,
)


class AssetGateway(Protocol):
    async def upload_image(self, **kwargs: object) -> dict[str, Any]: ...

    async def resize_image(self, **kwargs: object) -> dict[str, Any]: ...


@dataclass(frozen=True)
class RenditionPolicy:
    width: int
    height: int
    fit: str
    queue: ModerationQueue


POLICIES = {
    AssetKind.AVATAR: RenditionPolicy(512, 512, "cover", ModerationQueue.PLAYER_IDENTITY),
    AssetKind.EVENT_BANNER: RenditionPolicy(1600, 900, "cover", ModerationQueue.LIVE_EVENT),
    AssetKind.CREATOR_DECAL: RenditionPolicy(1024, 1024, "contain", ModerationQueue.CREATOR_MARKET),
}


class AssetPipeline:
    def __init__(self, gateway: AssetGateway) -> None:
        self.gateway = gateway
        self.moderation_items: list[ModerationItem] = []
        self.events: list[AssetProcessedEvent] = []

    async def process(self, request: AssetUploadRequest) -> AssetUploadResult:
        try:
            content = base64.b64decode(request.data_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("data_base64 must contain valid base64 image bytes") from exc

        policy = POLICIES[request.kind]
        uploaded = await self.gateway.upload_image(
            filename=request.filename,
            content_type=request.content_type,
            content=content,
            asset_id=request.asset_id,
        )
        stored = await self.gateway.resize_image(
            image=str(uploaded["url"]),
            width=policy.width,
            height=policy.height,
            fit=policy.fit,
            asset_id=request.asset_id,
        )

        queue = policy.queue if request.requires_moderation else None
        state = AssetState.QUEUED_FOR_REVIEW if queue else AssetState.READY
        if queue:
            self.moderation_items.append(
                ModerationItem(
                    asset_id=request.asset_id,
                    player_id=request.player_id,
                    queue=queue,
                )
            )
        self.events.append(
            AssetProcessedEvent(
                asset_id=request.asset_id,
                player_id=request.player_id,
                kind=request.kind,
                state=state,
                width=policy.width,
                height=policy.height,
                stored_image=stored,
            )
        )
        return AssetUploadResult(
            asset_id=request.asset_id,
            state=state,
            width=policy.width,
            height=policy.height,
            moderation_queue=queue,
            stored_image=stored,
        )
