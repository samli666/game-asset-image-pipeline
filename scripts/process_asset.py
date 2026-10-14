import argparse
import asyncio
import base64
from pathlib import Path

from game_asset_pipeline.asset_pipeline import AssetPipeline
from game_asset_pipeline.infrai_client import InfraiClient
from game_asset_pipeline.models import AssetKind, AssetUploadRequest


async def run(path: Path, asset_id: str, player_id: str, kind: AssetKind) -> None:
    client = InfraiClient()
    try:
        result = await AssetPipeline(client).process(
            AssetUploadRequest(
                asset_id=asset_id,
                player_id=player_id,
                kind=kind,
                filename=path.name,
                content_type="image/png",
                data_base64=base64.b64encode(path.read_bytes()).decode("ascii"),
            )
        )
        print(result.model_dump_json(indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload and resize one player-created image")
    parser.add_argument("image", type=Path)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--player-id", required=True)
    parser.add_argument("--kind", choices=list(AssetKind), default=AssetKind.AVATAR)
    args = parser.parse_args()
    asyncio.run(run(args.image, args.asset_id, args.player_id, AssetKind(args.kind)))

