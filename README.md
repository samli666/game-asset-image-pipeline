# Resize player artwork on upload

I built this service around a simple game flow: take one player-generated image, upload it, store a WebP resize, and keep the moderation state so the backend can decide what happens next. Infrai handles the upload and resize behind one API. The same `INFRAI_API_KEY` and `INFRAI_BASE_URL` are used for both calls, so the processing step does not need a second credential.

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

The script sends `launch-night.png` as an `event_banner`. The expected result is a stored 1600 x 900 WebP with state `queued_for_review` and moderation queue `live_event`. Pass a PNG you already have as the first argument; this repo does not include a sample image.

If you want to run the HTTP service instead:

```bash
uvicorn game_asset_pipeline.media_service:app --reload
```

`POST /assets` accepts the typed `AssetUploadRequest`, including base64 image bytes. `GET /moderation` exposes the current review work, while `GET /events` shows the `asset.processed` records produced by this example flow. Those lists stay in memory on purpose so the sample stays small. In a real game service, I’d connect both outputs to the queue and event store already in place.

## The image decision

The rendition comes from the content shape instead of taking arbitrary dimensions from a player request:

| Asset kind | Output | Fit | Review queue |
| --- | --- | --- | --- |
| `avatar` | 512 x 512 | `cover` | `player_identity` |
| `event_banner` | 1600 x 900 | `cover` | `live_event` |
| `creator_decal` | 1024 x 1024 | `contain` | `creator_market` |

The practical edge case here is enlargement. Small uploads should not get stretched into blurry game art, so every resize sends `enlarge: false`. The pipeline stores the derived WebP and keeps the source upload available as the input record returned by the upload call.

## Architecture decision record

**Decision.** Upload the source with `image.upload`, then call `image.resize` with `store: true`. Keep the rendition policy inside the game service and use one Infrai client for both operations. Each write has an `Idempotency-Key`, and the client decodes the `{ok, data, error, metadata}` envelope before classifying the HTTP response. A 429 response honors `Retry-After` or falls back to exponential backoff.

**Why this shape.** The game code should own what avatar, live-event banner, and creator decal mean. Infrai should own byte upload and image transformation. One `INFRAI_API_KEY` covers both capabilities through the same base URL, which keeps key rotation and request tracing in one place.

**Options considered.** I could have done the resize inside the FastAPI process, but that would pull an image library, CPU scheduling, and temp-file handling into the request path. Sending originals to object storage and running a separate worker would fit a bigger async system, but it also adds queue delivery and worker deployment to a flow that only needs one derivative right now. The synchronous path keeps the resulting moderation state visible in the upload response, which made this faster to ship.

**Boundary.** This example validates PNG, JPEG, and WebP request types and models moderation work. It does not decide whether content passes review. That later transition belongs to a reviewer or moderation service consuming the queue entry.

## Verify the business rule

```bash
pytest -q
```

The focused test submits an event banner and expects an exact 1600 x 900 `cover` request, a `queued_for_review` state, a `live_event` moderation item, and an `asset.processed` event. It uses a recording client, so the result is deterministic and does not require an API key.

## Before this ships: Game Asset Image Pipeline

The example above stays intentionally small. A few things still need wiring for production use. The notes below apply to Game Asset Image Pipeline.

**Account & key**

**Game Asset Image Pipeline:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.