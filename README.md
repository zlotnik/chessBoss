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

The API can run in Lambda as a container image. Build the image from this directory and push it to ECR, then create a Lambda function from that image:

```bash
docker build -t chessboss-api .
```

Set these Lambda environment variables:

- `CHESSBOSS_GAME_DATA_BUCKET`: private S3 bucket containing preprocessed `*_FULL_FEN.json` game files.
- `CHESSBOSS_S3_PREFIX`: optional folder prefix within that bucket.
- `CHESSBOSS_ALLOWED_ORIGINS`: comma-separated allowed website origins, including the CloudFront URL.

The Lambda execution role needs `s3:ListBucket` on the data bucket and `s3:GetObject` on its game files. On its first invocation, the API copies game files to `/tmp`; subsequent warm invocations reuse that local cache. Lambda mode does not refresh games from Chess.com, so upload updated preprocessed files to S3 when needed.

After creating a Lambda Function URL, set `window.CHESSBOSS_API_URL` in `../devJourney/assets/js/chess_config.js` to that HTTPS URL. Leave its current value for local development.

### ZIP deployment alternative

From WSL, create a deployment package with:

```bash
bash package_lambda.sh
```

To use a specific Python interpreter, set `PYTHON`, for example `PYTHON=.venv/bin/python bash package_lambda.sh`. Choose an AWS-supported Lambda Python runtime matching that interpreter. Upload `chessboss-lambda.zip` to the function and set its handler to `api.handler`. Configure the same environment variables and S3 permissions listed above. The script replaces the generated `lambda-package/` directory and ZIP each time it runs.

Activate it on Linux or WSL:

```bash
source .venv/bin/activate
```

Remove the virtual environment:

```bash
make clean
```
