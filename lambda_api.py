import os

os.environ.setdefault("CHESSBOSS_CACHE_DIR", "/tmp/chessboss-cache")

from api import app, handler