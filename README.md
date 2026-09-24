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

Activate it on Linux or WSL:

```bash
source .venv/bin/activate
```

Remove the virtual environment:

```bash
make clean
```
