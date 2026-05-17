import os
import sys
import urllib.request

port = os.environ.get('PORT', '3001')
url = f'http://127.0.0.1:{port}'

try:
    with urllib.request.urlopen(url) as response:
        if response.status != 200:
            sys.exit(1)
except Exception:
    sys.exit(1)
else:
    sys.exit(0)
