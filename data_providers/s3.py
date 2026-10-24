import os
from pathlib import Path
from typing import List

import boto3

from data_providers.base import (
    GameDataFilesNotFound,
    GameDataNotConfigured,
    GameDataProvider,
)
from search_games import CACHE_DIR, list_cached_month_files


class S3GameDataProvider(GameDataProvider):
    def __init__(self, bucket: str = "", prefix: str = "", client=None):
        self.bucket = bucket or os.environ.get("CHESSBOSS_GAME_DATA_BUCKET", "")
        self.prefix = (prefix or os.environ.get("CHESSBOSS_S3_PREFIX", "")).strip("/")
        if client is not None:
            self.client = client
        elif self.bucket:
            self.client = boto3.client("s3")
        else:
            self.client = None
        self._cache_loaded = False

    def cached_files(self, months: int) -> List[Path]:
        self._ensure_configured()
        return list_cached_month_files(months)

    def refresh(self, username: str, months: int) -> List[Path]:
        self._download_cache()
        cached_files = list_cached_month_files(months)
        if not cached_files:
            raise GameDataFilesNotFound("No *_FULL_FEN.json game files were found in the configured S3 bucket.")

        return cached_files

    def _download_cache(self) -> None:
        self._ensure_configured()
        client = self.client
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        paginator = client.get_paginator("list_objects_v2")
        prefix = ""
        if self.prefix:
            prefix = f"{self.prefix}/"
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item["Key"]
                if not key.endswith("_FULL_FEN.json"):
                    continue

                cache_path = CACHE_DIR / Path(key).name
                client.download_file(self.bucket, key, str(cache_path))

    def _ensure_configured(self) -> None:
        if not self.bucket or self.client is None:
            raise GameDataNotConfigured("CHESSBOSS_GAME_DATA_BUCKET is required when running in Lambda.")