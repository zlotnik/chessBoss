import json
from datetime import datetime, timezone
from pathlib import Path

import argparse
import chess


USERNAME = "WojoMc"
CACHE_DIR = Path(__file__).resolve().parent / "cached_games"

parser = argparse.ArgumentParser()
parser.add_argument("--username", default=USERNAME)
parser.add_argument("--fen", required=True)
parser.add_argument(
    "--months",
    type=int,
    default=6,
    help="Search only the most recent N cached months (default: 6)",
)


def list_cached_month_files(months=6):
    if not CACHE_DIR.exists():
        return []

    files = sorted(CACHE_DIR.glob("*_FULL_FEN.json"))
    if months is None or months <= 0:
        return files
    return files[-months:]


def normalize_fen(fen):
    """
    For position searching we can optionally ignore:
      - halfmove clock
      - fullmove number

    The first 4 FEN fields describe the actual position:
      board, side to move, castling rights, en passant
    """
    if not fen:
        return ""
    return " ".join(fen.split()[:4])


def format_game_date(game):
    raw_value = game.get("date") or game.get("end_time") or game.get("time_control")

    if raw_value is None:
        return "Unknown"

    if isinstance(raw_value, (int, float)):
        try:
            return datetime.fromtimestamp(raw_value, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except (OverflowError, OSError, ValueError):
            return str(raw_value)

    if isinstance(raw_value, str) and raw_value.isdigit():
        try:
            return datetime.fromtimestamp(int(raw_value), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except (OverflowError, OSError, ValueError):
            return raw_value

    return str(raw_value)


def format_game_result(game):
    result = game.get("result")
    if result is None:
        return "Unknown"

    mapping = {
        "win": "White win",
        "checkmated": "Checkmate",
        "resigned": "Resignation",
        "timeout": "Timeout",
        "stalemate": "Stalemate",
        "draw": "Draw",
        "agreed": "Draw by agreement",
        "repetition": "Draw by repetition",
        "insufficient": "Draw by insufficient material",
        "50move": "Draw by 50-move rule",
        "threecheck": "Three-check",
    }

    if isinstance(result, str):
        return mapping.get(result.lower(), result)

    return str(result)


def search_cached_games(target_fen, months=6):
    target = normalize_fen(target_fen)
    matches = []

    for month_file in list_cached_month_files(months):
        with open(month_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        for game in data.get("games", []):
            full_fen = game.get("full_fen", [])
            for move_number, fen in enumerate(full_fen):
                if normalize_fen(fen) == target:
                    board = chess.Board(fen)
                    matches.append((game, board, move_number))

    return matches


def main():
    args = parser.parse_args()

    username = args.username
    print(f"Searching cached games of {username}...")

    cached_files = list_cached_month_files(args.months)
    print(f"Found {len(cached_files)} cached month files.")

    matches = search_cached_games(args.fen, args.months)

    print()
    print(f"Found {len(matches)} matching positions.")

    for game, board, move_number in matches:
        print("=" * 60)

        white = game.get("white")
        black = game.get("black")
        white_name = white.get("username") if isinstance(white, dict) else white
        black_name = black.get("username") if isinstance(black, dict) else black

        print(f"{white_name} vs {black_name}")
        print(f"Date:   {format_game_date(game)}")
        print(f"Result: {format_game_result(game)}")
        print(f"Move:   {move_number}")

        print()
        print(board)

        print()
        print("FEN:")
        print(board.fen())


if __name__ == "__main__":
    main()
