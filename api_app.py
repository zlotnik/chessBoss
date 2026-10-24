import logging
import os
from typing import Any, Dict

import chess
import requests
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from cache import GameCache
from data_providers.base import (
    CacheState,
    GameDataFilesNotFound,
    GameDataNotConfigured,
    GameDataProvider,
)
from search_games import format_game_date, format_game_result


logger = logging.getLogger("uvicorn.error")


def serialize_match(game: Dict[str, Any], board: chess.Board, move_number: int) -> Dict[str, Any]:
    white = game.get("white")
    black = game.get("black")
    if isinstance(white, dict):
        white_name = white.get("username")
    else:
        white_name = white

    if isinstance(black, dict):
        black_name = black.get("username")
    else:
        black_name = black

    game_url = game.get("url")
    if game_url:
        game_url_with_move = f"{game_url}?move={move_number}"
    else:
        game_url_with_move = None

    return {
        "white": white_name,
        "black": black_name,
        "date": format_game_date(game),
        "result": format_game_result(game),
        "move": move_number,
        "url": game_url_with_move,
        "fen": board.fen(),
    }


def create_app(game_data_provider: GameDataProvider) -> FastAPI:
    cache = GameCache(game_data_provider)
    app = FastAPI(
        title="ChessBoss API",
        description="Search Chess.com games for chess positions.",
        version="1.0.0",
    )

    allowed_origins = [
        "http://localhost",
        "http://localhost:5500",
        "http://127.0.0.1",
        "http://127.0.0.1:5500",
        "null",
    ]
    allowed_origins.extend(
        origin.strip()
        for origin in os.environ.get("CHESSBOSS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/games")
    def games(
        fen: str = Query(..., description="FEN position to search for"),
        username: str = Query("WojoMc", description="Chess.com username"),
        months: int = Query(6, ge=1, description="Number of recent archive months"),
    ) -> Dict[str, Any]:
        try:
            chess.Board(fen)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"Invalid FEN: {error}") from error

        try:

            
            cache_status = cache.get_status(months)
            cache_age_minutes = cache.get_age_minutes()
            if cache_status == CacheState.EXISTING and cache_age_minutes > 60:
                cache_status = cache.refresh(username, months)
                cache_age_minutes = cache.get_age_minutes()

            if cache_status == CacheState.NOT_EXISTING:
                cache_status = cache.create(username, months)
                cache_age_minutes = cache.get_age_minutes()

            logger.info(
                "Cache ready: username=%s months=%d cached_months=%d newest_cache_age_minutes=%d refreshed=%s reason=%s files=%s",
                username,
                months,
                len(cache.cached_files),
                cache_age_minutes,
                cache.refreshed,
                cache.reason,
                [path.name for path in cache.cached_files],
            )

            matches = cache.search(fen, months)
            logger.info(
                "Game search complete: username=%s months=%d searched_months=%d matches=%d",
                username,
                months,
                len(cache.cached_files),
                len(matches),
            )
        except GameDataNotConfigured as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except GameDataFilesNotFound as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except requests.RequestException as error:
            logger.exception("Game search failed while refreshing cache: username=%s", username)
            raise HTTPException(status_code=502, detail=f"Unable to refresh games: {error}") from error
        except (BotoCoreError, ClientError) as error:
            logger.exception("Game search failed while loading S3 cache: username=%s", username)
            raise HTTPException(status_code=502, detail="Unable to load game data from S3.") from error
        except (OSError, ValueError) as error:
            logger.exception("Game search failed while reading or processing cache: username=%s", username)
            raise HTTPException(status_code=500, detail=str(error)) from error

        return {
            "username": username,
            "fen": fen,
            "months": months,
            "matches": [
                serialize_match(game, board, move_number)
                for game, board, move_number in matches
            ],
        }

    @app.post("/games/refresh")
    def refresh_games(
        username: str = Query("WojoMc", description="Chess.com username"),
        months: int = Query(6, ge=1, description="Number of recent archive months"),
    ) -> Dict[str, Any]:
        try:
            cache_status = cache.refresh(username, months)
        except GameDataNotConfigured as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except GameDataFilesNotFound as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except requests.RequestException as error:
            logger.exception("Explicit game cache refresh failed: username=%s", username)
            raise HTTPException(status_code=502, detail=f"Unable to refresh games: {error}") from error
        except (BotoCoreError, ClientError) as error:
            logger.exception("Explicit game cache refresh failed in S3: username=%s", username)
            raise HTTPException(status_code=502, detail="Unable to refresh game data from S3.") from error
        except (OSError, ValueError) as error:
            logger.exception("Explicit game cache refresh failed: username=%s", username)
            raise HTTPException(status_code=500, detail=str(error)) from error

        return {
            "username": username,
            "months": months,
            "status": cache_status.value,
            "refreshed": cache.refreshed,
            "cache_age_minutes": cache.get_age_minutes(),
            "cached_months": len(cache.cached_files),
        }

    return app