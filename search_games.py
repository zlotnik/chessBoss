import io
import json
from datetime import datetime, timezone
from pathlib import Path

import argparse
import chess
import chess.pgn
import requests


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
parser.add_argument(
    "--refresh",
    action="store_true",
    help="Refresh the cached month JSON and FEN data before searching",
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


def download_month_games(archive_url):
    response = requests.get(archive_url, headers={"User-Agent": "ChessGameDownloader/1.0"})
    response.raise_for_status()
    return response.json()


def save_month_games(archive_url, force_refresh=False):
    cache_dir = CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    month_key = archive_url.rstrip("/").split("/games/")[-1]
    cache_name = month_key.replace("/", "_") + ".json"
    cache_path = cache_dir / cache_name

    if cache_path.exists() and not force_refresh:
        return cache_path

    month_data = download_month_games(archive_url)
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(month_data, handle, indent=2)

    return cache_path


def game_to_fen_list(game_data):
    pgn = game_data.get("pgn")
    if not pgn:
        return []

    board = chess.Board()
    fen_history = [board.fen()]

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

    output_path = month_file.with_name(f"{month_file.stem}_FULL_FEN.json")
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(output_data, handle, indent=2)

    return output_path


def refresh_cached_games(username, months=6):
    archive_url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = requests.get(archive_url, headers={"User-Agent": "ChessGameDownloader/1.0"})
    response.raise_for_status()
    archives = response.json().get("archives", [])
    recent_archives = archives[-months:] if months and months > 0 else archives

    for archive in recent_archives:
        raw_file = save_month_games(archive, force_refresh=True)
        enrich_month_file(raw_file)


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

    if args.refresh or not list_cached_month_files(args.months):
        print("Refreshing cached games...")
        refresh_cached_games(username, args.months)

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
