import os
import sys
import urllib.error
import urllib.request

port = os.environ.get('PORT', '3001')
# `/` 404s on the backend (nginx owns the SPA path, not FastAPI) — but a
# 404 still proves the HTTP server is listening and routing, which is
# all this liveness probe needs to gate the frontend. We accept any
# response with status < 500 as "alive"; only a 5xx or a connection
# error (refused / timeout) counts as unhealthy. This makes the check
# resilient to route renames and to startup races on DB-backed
# endpoints like /api/setup-needed.
url = f'http://127.0.0.1:{port}/'

try:
    with urllib.request.urlopen(url, timeout=5) as response:
        sys.exit(0 if response.status < 500 else 1)
except urllib.error.HTTPError as exc:
    sys.exit(0 if exc.code < 500 else 1)
except Exception:
    sys.exit(1)
