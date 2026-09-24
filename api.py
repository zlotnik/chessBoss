from typing import Any, Dict

import chess
import requests
from fastapi import FastAPI, HTTPException, Query

from search_games import (
    format_game_date,
    format_game_result,
    list_cached_month_files,
    refresh_cached_games,
    search_cached_games,
)


app = FastAPI(
    title="ChessBoss API",
    description="Search Chess.com games for chess positions.",
    version="1.0.0",
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
        cached_files = list_cached_month_files(months)
        needs_refresh = refresh or not cached_files or len(cached_files) < months
        if needs_refresh:
            refresh_cached_games(username, months)
        matches = search_cached_games(fen, months)
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"Unable to refresh games: {error}") from error
    except (OSError, ValueError) as error:
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
