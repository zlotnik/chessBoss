# ChessBoss

## Setup

Create the virtual environment and install dependencies:

```bash
make install
```

Create only the virtual environment:

```bash
make venv
```

Download games:

```bash
./download_games --username WojoMc --months 6
```

Search games for a position:

```bash
./search_games --username WojoMc --fen "YOUR_FEN_HERE" --months 6
```

Start the FastAPI server:

```bash
./api
```

The interactive API documentation is available at <http://localhost:8000/docs>.
Search for a position with:

```text
GET /games?username=WojoMc&months=6&fen=rnbqkbnr%2Fpp1ppp1p%2F6p1%2F2p5%2F4P3%2F2P2N2%2FPP1P1PPP%2FRNBQKB1R%20b%20KQkq%20-%200%201
```

Activate it on Linux or WSL:

```bash
source .venv/bin/activate
```

Remove the virtual environment:

```bash
make clean
```
