import os
import tempfile
import time
import json


USERNAME = "WojoMc"
MONTHS = 6
FEN = "rnbqkbnr/pp1ppp1p/6p1/2p5/4P3/2P2N2/PP1P1PPP/RNBQKB1R b KQkq - 0 1"


def match_signature(matches):
    return [
        (game.get("url"), move_number, board.fen())
        for game, board, move_number in matches
    ]


def build_response(matches):
    from search_games import format_game_date, format_game_result

    serialized_matches = []
    for game, board, move_number in matches:
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
            game_url = f"{game_url}?move={move_number}"

        serialized_matches.append(
            {
                "white": white_name,
                "black": black_name,
                "date": format_game_date(game),
                "result": format_game_result(game),
                "move": move_number,
                "url": game_url,
                "fen": board.fen(),
            }
        )

    response = {
        "username": USERNAME,
        "fen": FEN,
        "months": MONTHS,
        "matches": serialized_matches,
    }
    return json.dumps(response, separators=(",", ":")).encode("utf-8")


def new_timings():
    return {
        "archive_api": 0.0,
        "monthly_downloads": 0.0,
        "fen_enrichment": 0.0,
        "file_search": 0.0,
        "response": 0.0,
    }


def report_timings(label, timings, total, archive_count, match_count, response_size):
    print(f"{label} cache:")
    print(f"  Chess.com archive-list API: {timings['archive_api']:.3f}s")
    print(f"  Monthly game downloads:    {timings['monthly_downloads']:.3f}s")
    print(f"  FEN enrichment:            {timings['fen_enrichment']:.3f}s")
    print(f"  File search:               {timings['file_search']:.3f}s")
    print(f"  Response serialization:    {timings['response']:.3f}s")
    print(
        f"  Total: {total:.3f}s; archives={archive_count}; "
        f"matches={match_count}; response={response_size} bytes"
    )


def main():
    with tempfile.TemporaryDirectory(prefix="chessboss-search-") as cache_directory:
        os.environ["CHESSBOSS_CACHE_DIR"] = cache_directory

        import search_games

        cold_timings = new_timings()
        hot_timings = new_timings()
        active_timings = [cold_timings]
        original_get = search_games.requests.get
        original_enrich = search_games.enrich_month_file

        def timed_get(url, *args, **kwargs):
            started_at = time.perf_counter()
            try:
                return original_get(url, *args, **kwargs)
            finally:
                elapsed = time.perf_counter() - started_at
                if url.endswith("/games/archives"):
                    active_timings[0]["archive_api"] += elapsed
                else:
                    active_timings[0]["monthly_downloads"] += elapsed

        def timed_enrich(month_file):
            started_at = time.perf_counter()
            try:
                return original_enrich(month_file)
            finally:
                active_timings[0]["fen_enrichment"] += time.perf_counter() - started_at

        search_games.requests.get = timed_get
        search_games.enrich_month_file = timed_enrich

        try:
            cold_started_at = time.perf_counter()
            cold_cache = search_games.prepare_cached_games(USERNAME, MONTHS)

            search_started_at = time.perf_counter()
            cold_matches = search_games.search_cached_games(FEN, MONTHS, username=USERNAME)
            cold_timings["file_search"] = time.perf_counter() - search_started_at

            response_started_at = time.perf_counter()
            cold_response = build_response(cold_matches)
            cold_timings["response"] = time.perf_counter() - response_started_at
            cold_elapsed = time.perf_counter() - cold_started_at

            if not cold_cache.cached_files:
                raise RuntimeError("The cold search did not download any game archives.")
            if not cold_matches:
                raise RuntimeError("The cold search found no matching games.")

            active_timings[0] = hot_timings
            hot_started_at = time.perf_counter()
            hot_cache = search_games.prepare_cached_games(USERNAME, MONTHS)

            search_started_at = time.perf_counter()
            hot_matches = search_games.search_cached_games(FEN, MONTHS, username=USERNAME)
            hot_timings["file_search"] = time.perf_counter() - search_started_at

            response_started_at = time.perf_counter()
            hot_response = build_response(hot_matches)
            hot_timings["response"] = time.perf_counter() - response_started_at
            hot_elapsed = time.perf_counter() - hot_started_at
        finally:
            search_games.requests.get = original_get
            search_games.enrich_month_file = original_enrich

        if hot_cache.refreshed:
            raise RuntimeError("The hot search unexpectedly refreshed the cache.")
        if match_signature(hot_matches) != match_signature(cold_matches):
            raise RuntimeError("Cold-cache and hot-cache search results differ.")
        if hot_response != cold_response:
            raise RuntimeError("Cold-cache and hot-cache responses differ.")

        report_timings(
            "Cold",
            cold_timings,
            cold_elapsed,
            len(cold_cache.cached_files),
            len(cold_matches),
            len(cold_response),
        )
        report_timings(
            "Hot",
            hot_timings,
            hot_elapsed,
            len(hot_cache.cached_files),
            len(hot_matches),
            len(hot_response),
        )


if __name__ == "__main__":
    main()