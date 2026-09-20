"""FastAPI entrypoint.

The app owns two things: a scheduler that regenerates the static tree, and a
static file server that serves that tree with pre-compressed bytes. There is no
database and no per-request rendering for the public pages.
"""

from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from starlette.staticfiles import StaticFiles

from utils import STATIC_DIR
from utils.logs import configure_logging, logger
from utils.utils import config, init_service, shutdown, update_epg
from utils.web import SecurityHeadersMiddleware, StaticCompressionMiddleware

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
	# Populate the files before the first request is served; the scheduler then
	# refreshes them on a fixed interval.
	await init_service()

	scheduler = AsyncIOScheduler()
	scheduler.add_job(
		update_epg,
		'interval',
		minutes=config.server.update_interval_minutes,
		max_instances=1,
	)
	scheduler.start()
	logger.info('Scheduler started', interval_minutes=config.server.update_interval_minutes)

	try:
		yield
	finally:
		scheduler.shutdown(wait=False)
		await shutdown()
		logger.info('Shutdown complete')


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get('/healthz', include_in_schema=False)
async def healthz() -> PlainTextResponse:
	# Liveness probe: never a full page render.
	return PlainTextResponse('ok')


# Order matters: middlewares added last are the outermost. Security headers wrap
# the compressed responses so every file gets them too.
app.add_middleware(StaticCompressionMiddleware, directory=STATIC_DIR)
app.add_middleware(SecurityHeadersMiddleware)

app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')


if __name__ == '__main__':
	uvicorn.run('app:app', host=config.server.host, port=config.server.port)
