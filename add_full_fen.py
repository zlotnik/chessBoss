import io
import json
import os
from pathlib import Path

import chess
import chess.pgn


CACHE_DIR = Path(__file__).resolve().parent / "cached_games"


def iter_month_json_files():
    if not CACHE_DIR.exists():
        return []
    return sorted(CACHE_DIR.glob("*.json"))


def game_to_fen_list(game_data):
    pgn = game_data.get("pgn")
    if not pgn:
        return []

    board = chess.Board()
    fen_history = []
    fen_history.append(board.fen())

    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return []

    if game is None:
        return []

    for move in game.mainline_moves():
        board.push(move)
        fen_history.append(board.fen())

    return fen_history


def enrich_month_file(month_file: Path):
    with month_file.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        return None

    games = data.get("games")
    if not isinstance(games, list):
        return None

    enriched_games = []
    for game in games:
        enriched_game = dict(game)
        enriched_game["full_fen"] = game_to_fen_list(game)
        enriched_games.append(enriched_game)

    output_data = dict(data)
    output_data["games"] = enriched_games

    month_key = month_file.stem
    target_name = f"{month_key}_FULL_FEN.json"
    target_path = month_file.with_name(target_name)

    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(output_data, handle, indent=2)

    return target_path


def main():
    month_files = iter_month_json_files()
    if not month_files:
        print("No cached month JSON files found.")
        return

    created = []
    for month_file in month_files:
        target_path = enrich_month_file(month_file)
        if target_path is not None:
            created.append(str(target_path.name))

    print(f"Created {len(created)} enriched files.")
    for item in created:
        print(item)


if __name__ == "__main__":
    main()
