import io
import json
from datetime import datetime, timezone
from pathlib import Path

import argparse
import chess
import chess.pgn
import requests
import time
from typing import Callable, List, NamedTuple, Optional


USERNAME = "WojoMc"
CACHE_DIR = Path(__file__).resolve().parent / "cached_games"
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60


class CachePreparation(NamedTuple):
    cached_files: List[Path]
    refreshed: bool
    reason: str
    cache_age_seconds: Optional[float]

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""Example:
  ./search_games --username WojoMc --fen "rnbqkbnr/pp1ppp1p/6p1/2p5/4P3/2P2N2/PP1P1PPP/RNBQKB1R b KQkq - 0 1" --months 6""",
)
parser.add_argument("--username", default=USERNAME)
parser.add_argument("--fen", required=True)
parser.add_argument(
    "--months",
    type=int,
    default=None,
    help="Search only the most recent N cached months; default: all cached months",
)
parser.add_argument(
    "--refresh",
    action="store_true",
    help="Refresh the cached month JSON and FEN data before searching",
)


def list_cached_month_files(months=None):
    if not CACHE_DIR.exists():
        return []

    files = sorted(CACHE_DIR.glob("*_FULL_FEN.json"))
    if months is None or months <= 0:
        return files
    return files[-months:]


def normalize_fen(fen):
    """
    Position lookup compares the visible board and side to move, ignoring:
    - castling rights
    - en passant target
    - halfmove clock
    - fullmove number
    """
    if not fen:
        return ""
    return " ".join(fen.split()[:2])


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

    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return []

    if game is None:
        return []

    board = game.board()
    fen_history = [board.fen()]

    for move in game.mainline_moves():
        try:
            board.push(move)
        except AssertionError:
            break
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
    skipped_games = 0

    for game in games:
        pgn_text = game.get("pgn")
        fen_list = game_to_fen_list(game)

        if pgn_text and not fen_list:
            skipped_games += 1
            game_url = game.get("url") or game.get("uuid") or "unknown game"
            print(f"Warning: skipping malformed PGN for {game_url} in {month_file.name}")
            continue

        enriched_game = dict(game)
        enriched_game["full_fen"] = fen_list
        enriched_games.append(enriched_game)

    if skipped_games:
        print(f"Warning: {skipped_games} malformed game(s) skipped in {month_file.name}")

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


def prepare_cached_games(
    username,
    months=6,
    force_refresh=False,
    on_refresh: Optional[Callable[[str], None]] = None,
):
    cached_files = list_cached_month_files(months)
    newest_cache_mtime = max((path.stat().st_mtime for path in cached_files), default=None)
    cache_age_seconds = time.time() - newest_cache_mtime if newest_cache_mtime is not None else None
    cache_is_stale = cache_age_seconds is None or cache_age_seconds >= CACHE_MAX_AGE_SECONDS
    cache_is_incomplete = (
        not cached_files
        or (months is not None and months > 0 and len(cached_files) < months)
    )
    needs_refresh = force_refresh or cache_is_stale or cache_is_incomplete

    if force_refresh:
        reason = "explicitly requested"
    elif cache_is_stale:
        reason = "cache is missing or older than 24 hours"
    elif cache_is_incomplete:
        reason = "fewer cached months than requested"
    else:
        reason = "cache is recent and complete"

    if needs_refresh:
        if on_refresh is not None:
            on_refresh(reason)
        refresh_cached_games(username, months)
        cached_files = list_cached_month_files(months)

    return CachePreparation(cached_files, needs_refresh, reason, cache_age_seconds)


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

    cache_status = prepare_cached_games(
        username,
        args.months,
        force_refresh=args.refresh,
        on_refresh=lambda reason: print(f"Refreshing cached games: {reason}..."),
    )

    if not cache_status.refreshed:
        print(f"Using cached games: {cache_status.reason}.")
    print(f"Found {len(cache_status.cached_files)} cached month files.")

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

        game_url = game.get("url", "N/A")
        if game_url != "N/A":
            game_url = f"{game_url}?move={move_number}"
        print(f"Link:   {game_url}")

        print()
        print(board)

        print()
        print("FEN:")
        print(board.fen())


if __name__ == "__main__":
    main()
