import logging
from typing import Any, Dict

import chess
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from search_games import (
    format_game_date,
    format_game_result,
    prepare_cached_games,
    search_cached_games,
)

logger = logging.getLogger("uvicorn.error")


app = FastAPI(
    title="ChessBoss API",
    description="Search Chess.com games for chess positions.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:5500", "http://127.0.0.1", "http://127.0.0.1:5500", "null"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_match(game: Dict[str, Any], board: chess.Board, move_number: int) -> Dict[str, Any]:
    white = game.get("white")
    black = game.get("black")
    white_name = white.get("username") if isinstance(white, dict) else white
    black_name = black.get("username") if isinstance(black, dict) else black
    game_url = game.get("url")

    return {
        "white": white_name,
        "black": black_name,
        "date": format_game_date(game),
        "result": format_game_result(game),
        "move": move_number,
        "url": f"{game_url}?move={move_number}" if game_url else None,
        "fen": board.fen(),
    }


@app.get("/games")
def games(
    fen: str = Query(..., description="FEN position to search for"),
    username: str = Query("WojoMc", description="Chess.com username"),
    months: int = Query(6, ge=1, description="Number of recent archive months"),
    refresh: bool = Query(False, description="Refresh cached games before searching"),
) -> Dict[str, Any]:
    try:
        chess.Board(fen)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"Invalid FEN: {error}") from error

    try:
        cache_status = prepare_cached_games(
            username,
            months,
            force_refresh=refresh,
            on_refresh=lambda reason: logger.info(
                "Refreshing cached games: username=%s months=%d reason=%s",
                username,
                months,
                reason,
            ),
        )
        cache_age_hours = cache_status.cache_age_seconds / 3600 if cache_status.cache_age_seconds is not None else None
        logger.info(
            "Cache ready: username=%s months=%d cached_months=%d newest_cache_age_hours=%s refreshed=%s reason=%s files=%s",
            username,
            months,
            len(cache_status.cached_files),
            f"{cache_age_hours:.1f}" if cache_age_hours is not None else "unknown",
            cache_status.refreshed,
            cache_status.reason,
            [path.name for path in cache_status.cached_files],
        )

        matches = search_cached_games(fen, months)
        logger.info(
            "Game search complete: username=%s months=%d searched_months=%d matches=%d",
            username,
            months,
            len(cache_status.cached_files),
            len(matches),
        )
    except requests.RequestException as error:
        logger.exception("Game search failed while refreshing cache: username=%s", username)
        raise HTTPException(status_code=502, detail=f"Unable to refresh games: {error}") from error
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
