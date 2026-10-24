import os

from api_app import create_app
from mangum import Mangum


IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
if IS_LAMBDA:
	from data_providers.s3 import S3GameDataProvider

	game_data_provider = S3GameDataProvider()
else:
	from data_providers.local import LocalGameDataProvider

	game_data_provider = LocalGameDataProvider()

app = create_app(game_data_provider)
handler = Mangum(app)
