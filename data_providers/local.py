import logging
from pathlib import Path
from typing import List

from data_providers.base import GameDataProvider
from search_games import list_cached_month_files, refresh_cached_games


logger = logging.getLogger("uvicorn.error")


class LocalGameDataProvider(GameDataProvider):
    def cached_files(self, months: int) -> List[Path]:
        return list_cached_month_files(months)

    def refresh(self, username: str, months: int) -> List[Path]:
        logger.info(
            "Refreshing cached games: username=%s months=%d",
            username,
            months,
        )
        refresh_cached_games(username, months)
        return list_cached_month_files(months)