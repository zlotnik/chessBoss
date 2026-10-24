import logging
import os
from pathlib import Path
from typing import Any, Dict

import chess
import boto3
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from botocore.exceptions import BotoCoreError, ClientError

from search_games import (
    CACHE_DIR,
    CachePreparation,
    format_game_date,
    format_game_result,
    list_cached_month_files,
    prepare_cached_games,
    search_cached_games,
)

logger = logging.getLogger("uvicorn.error")
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
GAME_DATA_BUCKET = os.environ.get("CHESSBOSS_GAME_DATA_BUCKET")
GAME_DATA_PREFIX = os.environ.get("CHESSBOSS_S3_PREFIX", "").strip("/")
S3_CLIENT = boto3.client("s3") if GAME_DATA_BUCKET else None
_s3_cache_loaded = False


def load_s3_game_cache() -> list[Path]:
    global _s3_cache_loaded

    if not GAME_DATA_BUCKET or S3_CLIENT is None:
        return []

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not _s3_cache_loaded:
        paginator = S3_CLIENT.get_paginator("list_objects_v2")
        prefix = f"{GAME_DATA_PREFIX}/" if GAME_DATA_PREFIX else ""
        for page in paginator.paginate(Bucket=GAME_DATA_BUCKET, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item["Key"]
                if not key.endswith("_FULL_FEN.json"):
                    continue

                cache_path = CACHE_DIR / Path(key).name
                if not cache_path.exists():
                    S3_CLIENT.download_file(GAME_DATA_BUCKET, key, str(cache_path))

        _s3_cache_loaded = True

    return list_cached_month_files()


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
        if IS_LAMBDA and not GAME_DATA_BUCKET:
            raise HTTPException(
                status_code=503,
                detail="CHESSBOSS_GAME_DATA_BUCKET is required when running in Lambda.",
            )
        if GAME_DATA_BUCKET:
            if refresh:
                raise HTTPException(
                    status_code=400,
                    detail="Refresh game data in S3 before searching; API refresh is disabled in Lambda mode.",
                )
            cached_files = load_s3_game_cache()
            if not cached_files:
                raise HTTPException(
                    status_code=503,
                    detail="No *_FULL_FEN.json game files were found in the configured S3 bucket.",
                )
            selected_files = cached_files[-months:] if months > 0 else cached_files
            cache_status = CachePreparation(selected_files, False, "loaded from S3", None)
        else:
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


handler = Mangum(app)
