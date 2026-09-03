import argparse
import json
import os
import requests


USERNAME = "WojoMc"
HEADERS = {"User-Agent": "ChessGameDownloader/1.0"}


def get_archives(username):
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json().get("archives", [])


def download_month_games(archive_url):
    response = requests.get(archive_url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def get_cache_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "cached_games")


def get_cache_path(archive_url):
    month_key = archive_url.rstrip("/").split("/games/")[-1]
    cache_name = month_key.replace("/", "_") + ".json"
    os.makedirs(get_cache_dir(), exist_ok=True)
    return os.path.join(get_cache_dir(), cache_name)


def save_month_games(archive_url, force_refresh=False):
    cache_path = get_cache_path(archive_url)

    if os.path.exists(cache_path) and not force_refresh:
        print(f"Using cached file: {cache_path}")
        return cache_path

    month_data = download_month_games(archive_url)

    with open(cache_path, "w", encoding="utf-8") as handle:
        json.dump(month_data, handle, indent=2)

    print(f"Saved: {cache_path}")
    return cache_path


def select_recent_archives(archives, months=6):
    if months is None or months <= 0:
        return archives
    return archives[-months:]


def main():
    parser = argparse.ArgumentParser(description="Download recent Chess.com game archives into a local cache.")
    parser.add_argument("--username", default=USERNAME, help="Chess.com username")
    parser.add_argument("--months", type=int, default=6, help="Download only the last N archive months (default: 6)")
    parser.add_argument("--all", action="store_true", help="Download every archive month instead of only the last N")
    parser.add_argument("--refresh", action="store_true", help="Ignore the cache and re-download files")
    args = parser.parse_args()

    archives = get_archives(args.username)
    if not archives:
        print(f"No archive months found for {args.username}.")
        return

    if args.all:
        selected_archives = archives
    else:
        selected_archives = select_recent_archives(archives, args.months)

    print(f"Found {len(archives)} archive months total.")
    print(f"Downloading {len(selected_archives)} month(s) to cache.")

    for archive_url in selected_archives:
        save_month_games(archive_url, force_refresh=args.refresh)

    print("Done.")


if __name__ == "__main__":
    main()
