import io
import requests
import chess
import chess.pgn
import argparse


USERNAME = "WojoMc"

parser = argparse.ArgumentParser()
parser.add_argument("--username", default=USERNAME)
parser.add_argument("--fen", required=True)
parser.add_argument(
    "--months",
    type=int,
    default=6,
    help="Search only the most recent N archive months (default: 6)",
)


HEADERS = {
    "User-Agent": "ChessPositionSearcher/1.0"
}


def get_archives(username):
    url = f"https://api.chess.com/pub/player/{username}/games/archives"

    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    return response.json()["archives"]


def download_month_pgn(url):
    response = requests.get(url + "/pgn", headers=HEADERS)
    response.raise_for_status()

    return response.text


def normalize_fen(fen):
    """
    For position searching we can optionally ignore:
      - halfmove clock
      - fullmove number

    The first 4 FEN fields describe the actual position:
      board, side to move, castling rights, en passant
    """
    return " ".join(fen.split()[:4])


def search_pgn(pgn_text, target_fen):
    target = normalize_fen(target_fen)

    pgn_file = io.StringIO(pgn_text)

    while True:
        game = chess.pgn.read_game(pgn_file)

        if game is None:
            break

        board = game.board()

        # Check the initial position
        if normalize_fen(board.fen()) == target:
            yield game, board.copy(), 0

        for move_number, move in enumerate(game.mainline_moves(), start=1):
            board.push(move)

            if normalize_fen(board.fen()) == target:
                yield game, board.copy(), move_number


def select_recent_archives(archives, months=6):
    if months is None or months <= 0:
        return archives
    return archives[-months:]


def main():
    args = parser.parse_args()

    username = args.username
    print(f"Searching games of {username}...")

    all_archives = get_archives(username)
    archives = select_recent_archives(all_archives, args.months)

    print(f"Found {len(all_archives)} months total; searching the last {len(archives)} months.")

    matches = []

    for i, archive_url in enumerate(archives, start=1):

        print(f"[{i}/{len(archives)}] {archive_url}")

        try:
            pgn_text = download_month_pgn(archive_url)

            for game, board, move_number in search_pgn(
                pgn_text,
                args.fen,
            ):
                matches.append((game, board, move_number))

        except requests.HTTPError as e:
            print(f"  Error: {e}")

    print()
    print(f"Found {len(matches)} matching positions.")

    for game, board, move_number in matches:

        print("=" * 60)

        print(
            f"{game.headers.get('White')} "
            f"vs "
            f"{game.headers.get('Black')}"
        )

        print(f"Date:   {game.headers.get('Date')}")
        print(f"Result: {game.headers.get('Result')}")
        print(f"Move:   {move_number}")

        print()
        print(board)

        print()
        print("FEN:")
        print(board.fen())


if __name__ == "__main__":
    main()
