"""
Gunicorn configuration for FreshDash backend.
Optimized for production deployments using SQLite3 with Write-Ahead Logging (WAL).
"""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# For SQLite3, use multi-threaded workers (gthread) to allow high concurrent read
# throughput without spawning too many separate process writers competing for file locks.
workers = int(os.environ.get("GUNICORN_WORKERS", 2))
threads = int(os.environ.get("GUNICORN_THREADS", 4))
worker_class = "gthread"

# Request timeouts & keepalive
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 60))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 50))

# Process naming
proc_name = "freshdash_api"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()

