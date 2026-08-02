import os
import sys
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "src", "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, "src", "backend", ".env"))

# a2wsgi.ASGIMiddleware spins up a background asyncio event-loop thread when it
# is constructed. LSAPI imports this module once and then forks its workers, and
# threads do not survive fork() - the child would inherit a loop object with no
# thread driving it and every request would block forever. So build it lazily,
# on first request, which happens inside the already-forked worker.
_application = None
_lock = threading.Lock()


def application(environ, start_response):
    global _application
    if _application is None:
        with _lock:
            if _application is None:
                from a2wsgi import ASGIMiddleware
                from app.main import app as fastapi_app
                _application = ASGIMiddleware(fastapi_app)
    return _application(environ, start_response)
