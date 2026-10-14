from fastapi import FastAPI, HTTPException

from .asset_pipeline import AssetPipeline
from .infrai_client import InfraiClient, InfraiError
from .models import AssetProcessedEvent, AssetUploadRequest, AssetUploadResult, ModerationItem


app = FastAPI(title="Game asset image pipeline")
client = InfraiClient()
pipeline = AssetPipeline(client)


@app.post("/assets", response_model=AssetUploadResult)
async def upload_asset(request: AssetUploadRequest) -> AssetUploadResult:
    try:
        return await pipeline.process(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@app.get("/moderation", response_model=list[ModerationItem])
async def moderation_queue() -> list[ModerationItem]:
    return pipeline.moderation_items


@app.get("/events", response_model=list[AssetProcessedEvent])
async def processed_events() -> list[AssetProcessedEvent]:
    return pipeline.events


@app.on_event("shutdown")
async def close_client() -> None:
    await client.close()

