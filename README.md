# ChessBoss

## How to run backend + front end

1. run chess api in chess boss
```bash
cd ~/chessBoss
make install
./api
```

2. run front end server
```bash
cd ~/devJourney
python3 -m http.server 5500
```

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

## AWS Lambda deployment

The API uses the same routes and search logic in both environments. `api.py` selects the S3 provider when Lambda sets `AWS_LAMBDA_FUNCTION_NAME`; otherwise it selects the local provider. Local Uvicorn serves `api:app`; Lambda uses `lambda_api.handler`, which sets the writable `/tmp/chessboss-cache` directory and wraps the shared FastAPI app with Mangum.

Set these Lambda environment variables:

- `CHESSBOSS_GAME_DATA_BUCKET`: private S3 bucket containing preprocessed `*_FULL_FEN.json` game files.
- `CHESSBOSS_S3_PREFIX`: optional folder prefix within that bucket.
- `CHESSBOSS_ALLOWED_ORIGINS`: comma-separated allowed website origins, including the CloudFront URL.

The Lambda execution role needs `s3:ListBucket` on the data bucket, plus `s3:GetObject` and `s3:PutObject` on its game files. The lookup order is `/tmp`, then S3 if the local cache is missing or incomplete, then Chess.com if S3 cannot satisfy the requested months. Cached S3 object timestamps are preserved when files are restored so the one-hour freshness check remains accurate. When Lambda refreshes from Chess.com, it writes the generated `*_FULL_FEN.json` files back to S3. Lambda must have outbound internet access to Chess.com; a function attached to a VPC may need a NAT gateway. Local mode refreshes from Chess.com automatically when its cache is missing or older than one hour.

Normal searches use `GET /games`. To force a cache refresh, use `POST /games/refresh?username=WojoMc&months=6`.

After creating a Lambda Function URL, set `window.CHESSBOSS_API_URL` in `../devJourney/assets/js/chess_config.js` to that HTTPS URL. Leave its current value for local development.

### Build deployment package

From WSL, create a deployment package with:

```bash
bash package_lambda.sh
```

To use a specific Python interpreter, set `PYTHON`, for example `PYTHON=.venv/bin/python bash package_lambda.sh`. Choose an AWS-supported Lambda Python runtime matching that interpreter. Upload `chessboss-lambda.zip` to the function and set its handler to `lambda_api.handler`. Configure the same environment variables and S3 permissions listed above. The script replaces the generated `lambda-package/` directory and ZIP each time it runs.

The Lambda ZIP uses `requirements-lambda.txt` and omits Uvicorn plus the local-only provider module. Local development continues to use the full `requirements.txt`.

Activate it on Linux or WSL:

```bash
source .venv/bin/activate
```

Remove the virtual environment:

```bash
make clean
```
