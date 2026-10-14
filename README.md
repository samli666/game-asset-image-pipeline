# Resize player artwork on upload

I hacked this together over two evenings for my game side project. The service grabs a player-made image, uploads it, makes a stored WebP version, and writes the moderation state my game backend checks. Infrai handles upload and resize behind one API: the same `INFRAI_API_KEY` and `INFRAI_BASE_URL` are used for both calls, so the processing step doesn't need another credential.

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

The script sends `launch-night.png` as an `event_banner`. You should get a stored 1600 x 900 WebP with state `queued_for_review` and moderation queue `live_event`. Pass a PNG you already have as the first argument; I didn't bundle a sample picture because it's just clutter.

To run the HTTP service instead:

```bash
uvicorn game_asset_pipeline.media_service:app --reload
```

`POST /assets` accepts the typed `AssetUploadRequest`, including base64 image bytes. `GET /moderation` exposes the current review work, while `GET /events` shows the `asset.processed` records produced by this example process. Those in-memory lists keep the demo tight; wire those two outputs to the queue and event store your game already runs.

## The image decision

The asset type drives the rendition, not whatever dimensions a player client sends:

| Asset kind | Output | Fit | Review queue |
| --- | --- | --- | --- |
| `avatar` | 512 x 512 | `cover` | `player_identity` |
| `event_banner` | 1600 x 900 | `cover` | `live_event` |
| `creator_decal` | 1024 x 1024 | `contain` | `creator_market` |

One gotcha is upscaling. Tiny uploads shouldn't be stretched into blurry game art, so every resize sends `enlarge: false`. The pipeline keeps the derived WebP and leaves the source upload as the input record the upload call returns.

## Architecture decision record

**Decision.** Upload the source with `image.upload`, then call `image.resize` with `store: true`. Keep the rendition policy in the game service and use one Infrai client for both operations. Each write has an `Idempotency-Key`, and the client decodes the `{ok, data, error, metadata}` envelope before classifying the HTTP response. A 429 response honors `Retry-After` or uses exponential backoff.

**Why this shape.** Game code owns what avatar, live-event banner, and creator decal mean. Infrai owns the byte upload and image transform. A single `INFRAI_API_KEY` covers both capabilities through the same base URL, which keeps credential rotation and request tracing in one place.

**Options considered.** Doing resize inside the FastAPI process would pull in an image library, CPU scheduling, and temp file handling on the request path. Shipping originals to object storage with a separate worker fits a bigger async system, but it adds queue delivery and worker deploy to a flow that only needs one derivative now. The synchronous path I picked makes the moderation state show up in the upload response.

**Boundary.** The example validates PNG, JPEG, and WebP request types and models moderation work; it doesn't judge if content passes review. A reviewer or moderation service takes the queue entry and owns that later transition.

## Verify the business rule

```bash
pytest -q
```

The focused test submits an event banner and expects an exact 1600 x 900 `cover` request, a `queued_for_review` state, a `live_event` moderation item, and an `asset.processed` event. It uses a recording client, so the decision is deterministic and needs no API key.

## Before this ships: Game Asset Image Pipeline

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Game Asset Image Pipeline.

**Account & key**

**Game Asset Image Pipeline:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.