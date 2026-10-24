import time
from math import ceil
from pathlib import Path
from typing import List, Optional

from data_providers.base import CacheState, CacheStatus, GameDataProvider
from search_games import search_cached_games


class GameCache:
    def __init__(self, provider: GameDataProvider):
        self.provider = provider
        self._status = CacheStatus([], False, None)

    def get_status(self, months: int) -> CacheState:
        cached_files = self.provider.cached_files(months)
        return self._update_status(cached_files, False)

    def get_age_minutes(self) -> int:
        if self._status.cache_age_seconds is None:
            return 0
        return ceil(self._status.cache_age_seconds / 60)

    def create(self, username: str, months: int) -> CacheState:
        cached_files = self.provider.refresh(username, months)
        return self._update_status(cached_files, True)

    def refresh(self, username: str, months: int) -> CacheState:
        cached_files = self.provider.refresh(username, months)
        return self._update_status(cached_files, True)

    @property
    def cached_files(self) -> List[Path]:
        return self._status.cached_files

    @property
    def refreshed(self) -> bool:
        return self._status.refreshed

    @property
    def reason(self) -> str:
        return self._status.reason

    def search(self, fen: str, months: int):
        return search_cached_games(fen, months)

    def _age_seconds(self, cached_files: List[Path]) -> Optional[float]:
        newest_cache_mtime = None
        if cached_files:
            newest_cache_mtime = max(path.stat().st_mtime for path in cached_files)
        if newest_cache_mtime is None:
            return None
        return max(time.time() - newest_cache_mtime, 0)

    def _make_status(self, cached_files: List[Path], refreshed: bool) -> CacheStatus:
        return CacheStatus(cached_files, refreshed, self._age_seconds(cached_files))

    def _update_status(self, cached_files: List[Path], refreshed: bool) -> CacheState:
        self._status = self._make_status(cached_files, refreshed)
        if self._status.exists:
            return CacheState.EXISTING
        return CacheState.NOT_EXISTING