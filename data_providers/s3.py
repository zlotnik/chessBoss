import os
from pathlib import Path
from typing import List

import boto3

from data_providers.base import (
    GameDataFilesNotFound,
    GameDataNotConfigured,
    GameDataProvider,
)
from search_games import CACHE_DIR, list_cached_month_files, refresh_cached_games


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
    def cached_files(self, months: int) -> List[Path]:
        self._ensure_configured()
        cached_files = list_cached_month_files(months)
        if self._has_enough_files(cached_files, months):
            return cached_files

        cached_files = self._restore_cache_from_s3(months)
        if self._has_enough_files(cached_files, months):
            return cached_files
        return []

    def refresh(self, username: str, months: int) -> List[Path]:
        self._ensure_configured()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        refresh_cached_games(username, months)
        cached_files = list_cached_month_files(months)
        if not cached_files:
            raise GameDataFilesNotFound("No *_FULL_FEN.json game files were downloaded from Chess.com.")

        client = self.client
        for cache_path in cached_files:
            key = cache_path.name
            if self.prefix:
                key = f"{self.prefix}/{key}"
            with cache_path.open("rb") as cache_file:
                client.put_object(Bucket=self.bucket, Key=key, Body=cache_file)

        return cached_files

    def _has_enough_files(self, cached_files: List[Path], months: int) -> bool:
        if months <= 0:
            return bool(cached_files)
        return len(cached_files) >= months

    def _restore_cache_from_s3(self, months: int) -> List[Path]:
        self._ensure_configured()
        client = self.client
        paginator = client.get_paginator("list_objects_v2")
        prefix = ""
        if self.prefix:
            prefix = f"{self.prefix}/"

        s3_files = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                if item["Key"].endswith("_FULL_FEN.json"):
                    s3_files.append(item)

        s3_files.sort(key=lambda item: item["Key"])
        if months > 0:
            s3_files = s3_files[-months:]
        if not s3_files:
            return list_cached_month_files(months)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for item in s3_files:
            key = item["Key"]
            cache_path = CACHE_DIR / Path(key).name
            client.download_file(self.bucket, key, str(cache_path))
            last_modified = item.get("LastModified")
            if last_modified is not None:
                modified_time = last_modified.timestamp()
                os.utime(cache_path, (modified_time, modified_time))

        return list_cached_month_files(months)

    def _ensure_configured(self) -> None:
        if not self.bucket or self.client is None:
            raise GameDataNotConfigured("CHESSBOSS_GAME_DATA_BUCKET is required when running in Lambda.")