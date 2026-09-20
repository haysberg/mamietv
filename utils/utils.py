"""Service orchestration: fetch once at startup, then on a schedule."""

import asyncio
from datetime import datetime

from utils import CONFIG_FILE
from utils.config import Config, load_config
from utils.images import localize_icons
from utils.logs import logger
from utils.render import precompress_assets, write_site
from utils.xmltv import PARIS, build_epg, close_client, fetch_xml, get_client

config: Config = load_config(CONFIG_FILE)

# A single writer at a time: a slow fetch must not overlap the next interval.
_lock = asyncio.Lock()


async def update_epg() -> None:
	"""Fetch the guide and regenerate the static files.

	A conditional GET (ETag / Last-Modified) makes the common case cheap: when
	the origin answers 304 we keep the files already on disk untouched.
	"""
	async with _lock:
		xml = await fetch_xml(config)
		if xml is None:
			logger.info('Guide unchanged (304 Not Modified)')
			return

		now = datetime.now(PARIS)
		epg = build_epg(xml, config, now)
		if not epg['channels']:
			logger.warning('No programs found for the evening window', day=epg['day'])
			return

		# Serve logos from our own origin: the upstream hosts are flaky and often
		# blocked by browser tracking protection.
		icons = await localize_icons(epg['channels'], get_client())

		# brotli x11 and minify-html are CPU-bound; keep them off the event loop.
		summary = await asyncio.to_thread(write_site, epg)
		logger.info('Evening guide updated', day=epg['day'], icons=icons, **summary)


async def init_service() -> None:
	# Assets are committed, so their `.br`/`.gz` siblings are built once here.
	count = await asyncio.to_thread(precompress_assets)
	if count:
		logger.info('Pre-compressed static assets', count=count)
	await update_epg()


async def shutdown() -> None:
	await close_client()
