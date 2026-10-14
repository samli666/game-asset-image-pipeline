from enum import StrEnum
from typing import Any

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # Keep domain-only tests runnable without service extras.
    def Field(default: Any = ..., **_: Any) -> Any:
        return default

    class BaseModel:
        def __init__(self, **values: Any) -> None:
            fields: dict[str, Any] = {}
            for cls in reversed(type(self).__mro__):
                fields.update(getattr(cls, "__annotations__", {}))
            missing = []
            for name in fields:
                if name in values:
                    setattr(self, name, values.pop(name))
                elif hasattr(type(self), name) and getattr(type(self), name) is not ...:
                    setattr(self, name, getattr(type(self), name))
                else:
                    missing.append(name)
            if missing or values:
                details = [*(f"missing {name}" for name in missing), *(f"unexpected {name}" for name in values)]
                raise TypeError(", ".join(details))

        def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
            del mode
            return {name: getattr(self, name) for name in self.__annotations__}


class AssetKind(StrEnum):
    AVATAR = "avatar"
    EVENT_BANNER = "event_banner"
    CREATOR_DECAL = "creator_decal"


class ModerationQueue(StrEnum):
    PLAYER_IDENTITY = "player_identity"
    LIVE_EVENT = "live_event"
    CREATOR_MARKET = "creator_market"


class AssetState(StrEnum):
    QUEUED_FOR_REVIEW = "queued_for_review"
    READY = "ready"


class AssetUploadRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=80)
    player_id: str = Field(min_length=1, max_length=80)
    kind: AssetKind
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(pattern=r"^image/(png|jpeg|webp)$")
    data_base64: str = Field(min_length=1)
    requires_moderation: bool = True


class LiveEvent(BaseModel):
    event_id: str
    title: str
    banner_asset_id: str
    opens_at: str


class ModerationItem(BaseModel):
    asset_id: str
    player_id: str
    queue: ModerationQueue


class AssetProcessedEvent(BaseModel):
    event_type: str = "asset.processed"
    asset_id: str
    player_id: str
    kind: AssetKind
    state: AssetState
    width: int
    height: int
    stored_image: dict[str, object]


class AssetUploadResult(BaseModel):
    asset_id: str
    state: AssetState
    width: int
    height: int
    moderation_queue: ModerationQueue | None
    stored_image: dict[str, object]
