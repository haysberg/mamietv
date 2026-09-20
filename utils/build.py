"""Build the publishable site once: fetch, parse, download logos, render."""

import asyncio
import os
from datetime import datetime

from utils import CONFIG_FILE, DIST_DIR
from utils.config import Config, load_config
from utils.images import localize_icons
from utils.logs import logger
from utils.render import copy_assets, write_site
from utils.xmltv import PARIS, build_epg, close_client, fetch_xml, get_client

config: Config = load_config(CONFIG_FILE)


async def build(dest: str = DIST_DIR) -> dict:
	"""Regenerate the whole `dest` tree from the current guide."""
	xml = await fetch_xml(config)
	if xml is None:
		raise RuntimeError('guide unchanged and no cached copy available')

	epg = build_epg(xml, config, datetime.now(PARIS))
	if not epg['channels']:
		raise RuntimeError('no programs found in the evening window')

	# Lay down the committed assets, drop in the logos, then render on top.
	await asyncio.to_thread(copy_assets, dest)
	icons = await localize_icons(epg['channels'], get_client(), os.path.join(dest, 'channels'))
	# minify-html is CPU-bound; keep it off the event loop.
	summary = await asyncio.to_thread(write_site, epg, dest)
	await close_client()

	logger.info('Site generated', day=epg['day'], icons=icons, dist=dest, **summary)
	return summary
