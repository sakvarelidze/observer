import os

DEFAULT_INTERVAL_SECONDS = int(os.getenv("DEFAULT_INTERVAL_SECONDS", "30"))
MIN_INTERVAL_SECONDS = 5  # hard floor to avoid thrash
