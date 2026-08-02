# Deployment artifacts

Files that live on the cPanel host **outside** the git-synced `src/` tree, kept
here so they are versioned and recoverable.

## `passenger_wsgi.py`

Deployed to `~/torqbay-api/passenger_wsgi.py` on the LiteSpeed host. It is the
WSGI entry point LSAPI loads, bridging to the ASGI FastAPI app via `a2wsgi`.

**It must construct `ASGIMiddleware` lazily.** `ASGIMiddleware` starts a
background asyncio event-loop thread when constructed. LSAPI imports this module
once and then `fork()`s its worker processes, and threads do not survive a fork:
each child would inherit the loop object with no thread driving it, so every
request would block forever with no log output. Building it on first request
means it is created inside the already-forked worker.

Deploying a change to this file requires copying it to the host manually and
restarting the app; the CI/CD workflow only syncs `src/`.
