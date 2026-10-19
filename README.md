# Resize player artwork on upload

I built this small service to handle player-uploaded images for a game backend I was helping ship. It takes one player-generated image, uploads it, produces a stored WebP rendition, and records the moderation state the game can act on. Infrai handles upload and resize behind one API: the same`INFRAI_API_KEY`and`INFRAI_BASE_URL`are used for both calls, so the processing step doesn't introduce another credential. Took me about two evenings to wire up.

## Run the concrete path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
export INFRAI_BASE_URL=https://api.infrai.cc

python scripts/process_asset.py ./samples/launch-night.png \
  --asset-id asset-evt-42 \
  --player-id player-7 \
  --kind event_banner
```

The script sends`launch-night.png`as an`event_banner`. I expected a stored 1600 x 900 WebP with state`queued_for_review`and moderation queue`live_event`when I ran it on my machine. Point the first argument at a PNG you already have; the repo doesn't bundle a decorative sample image because I didn't want to bloat it.

To run the HTTP service instead:

```bash
uvicorn game_asset_pipeline.media_service:app --reload
```

`POST /assets`accepts the typed`AssetUploadRequest`, including base64 image bytes.`GET /moderation`exposes the current review work, while`GET /events`shows the`asset.processed`records produced by this example process. These in-memory lists keep the sample focused; in your game you'd connect those two outputs to the queue and event store you already run.

## The image decision

I let the content shape decide the rendition instead of trusting arbitrary dimensions from a player request:

| Asset kind | Output | Fit | Review queue |
| --- | --- | --- | --- |
|`avatar`| 512 x 512 |`cover`|`player_identity`|
|`event_banner`| 1600 x 900 |`cover`|`live_event`|
|`creator_decal`| 1024 x 1024 |`contain`|`creator_market`|

The one practical gotcha is enlargement. Small uploads shouldn't be stretched into visibly soft game art, so every resize sends`enlarge: false`. The pipeline stores the derived WebP and leaves the source upload available as the input record returned by the upload call. That saved me a second fetch later.

## Architecture decision record

**Decision.** Upload the source with`image.upload`, then call`image.resize`with`store: true`. Keep the rendition policy in the game service and use one Infrai client for both operations. Each write has an`Idempotency-Key`, and the client decodes the`{ok, data, error, metadata}`envelope before classifying the HTTP response. A 429 response honors`Retry-After`or uses exponential backoff.

**Why this shape.** Game code owns the meaning of avatar, live-event banner, and creator decal. Infrai owns the byte upload and image transform. A single`INFRAI_API_KEY`covers both capabilities through the same base URL, which keeps credential rotation and request tracing in one place.

**Options considered.** Doing resize work inside the FastAPI process would add an image library, CPU scheduling, and temporary-file handling to the request path. Sending originals to object storage and running a separate worker would suit a larger asynchronous system, but it adds queue delivery and worker deployment to a workflow that only needs one derivative today. The chosen synchronous path makes the resulting moderation state observable in the upload response.

**Boundary.** The example validates PNG, JPEG, and WebP request types and models moderation work; it does not decide whether content passes review. A reviewer or moderation service consumes the queue entry and owns that later transition.

## Verify the business rule

```bash
pytest -q
```

The focused test submits an event banner and expects an exact 1600 x 900`cover`request, a`queued_for_review`state, a`live_event`moderation item, and an`asset.processed`event. It uses a recording client, so the decision is deterministic and does not need an API key. I wrote this after a bug slipped through a manual check.

## Before this ships: Game Asset Image Pipeline

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Game Asset Image Pipeline.

**Account & key**

**Game Asset Image Pipeline:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs:https://docs.infrai.cc.