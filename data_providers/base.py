from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional


CACHE_MAX_AGE_SECONDS = 60 * 60


class CacheState(Enum):
    EXISTING = "existing"
    NOT_EXISTING = "not_existing"


@dataclass(frozen=True)
class CacheStatus:
    cached_files: List[Path]
    refreshed: bool
    cache_age_seconds: Optional[float]

    @property
    def exists(self) -> bool:
        return bool(self.cached_files)

    @property
    def is_out_of_date(self) -> bool:
        if not self.exists:
            return False
        if self.cache_age_seconds is None:
            return True
        return self.cache_age_seconds > CACHE_MAX_AGE_SECONDS

    @property
    def age_hours(self) -> Optional[float]:
        if self.cache_age_seconds is None:
            return None
        return self.cache_age_seconds / 3600

    @property
    def reason(self) -> str:
        if not self.exists:
            return "cache is missing"
        if self.refreshed:
            return "cache refreshed"
        if self.is_out_of_date:
            return "cache is older than 1 hour"
        return "cache is recent"


class GameDataError(Exception):
    pass


class GameDataNotConfigured(GameDataError):
    pass


class GameDataFilesNotFound(GameDataError):
    pass


class GameDataProvider(ABC):
    @abstractmethod
    def cached_files(self, months: int) -> List[Path]:
        raise NotImplementedError

    @abstractmethod
    def refresh(self, username: str, months: int) -> List[Path]:
        raise NotImplementedError