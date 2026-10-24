import os

os.environ["CHESSBOSS_CACHE_DIR"] = "/tmp/chessboss-cache"

from api import app
from mangum import Mangum


handler = Mangum(app)