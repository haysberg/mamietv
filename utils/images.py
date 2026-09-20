"""Download channel logos so the published site never hits third-party hosts.

Hotlinking `programme-tv.net` is fragile (tracking protection, CDNs, referrer
rules) and heavy (the default logo is 480x480, ~130 kB). The build fetches a
small variant once, writes it under `dist/channels/`, and rewrites the JSON to a
relative `channels/...` path.
"""

import asyncio
import os
import re

import httpx

from utils import DIST_DIR
from utils.logs import logger

# programme-tv.net serves every size from the same URL by swapping the
# "/<w>x<h>/quality/<q>/" segment. Requesting 96x96 drops each logo from
# ~130 kB to ~6 kB, which is plenty for the 40 px slot it is shown in.
_SIZE_RE = re.compile(r'/\d+x\d+/quality/\d+(?=/)')
_EXT_RE = re.compile(r'\.(png|jpe?g|gif|webp|svg)(?:[?#]|$)', re.IGNORECASE)


def _small_variant(url: str) -> str:
	return _SIZE_RE.sub('/96x96/quality/80', url)


def _filename(channel_id: str, url: str) -> str:
	safe = re.sub(r'[^A-Za-z0-9]+', '_', channel_id).strip('_') or 'channel'
	match = _EXT_RE.search(url)
	ext = match.group(1).lower() if match else 'png'
	return f'{safe}.{"jpg" if ext == "jpeg" else ext}'


async def _download(client: httpx.AsyncClient, channel: dict, channel_dir: str) -> None:
	filename = _filename(channel['id'], channel['icon'])
	path = os.path.join(channel_dir, filename)
	local_url = f'channels/{filename}'

	if os.path.exists(path) and os.path.getsize(path) > 0:
		channel['icon'] = local_url
		return

	try:
		response = await client.get(_small_variant(channel['icon']))
		response.raise_for_status()
	except (httpx.HTTPError, ValueError) as exc:
		# Keep the remote URL as a fallback rather than dropping the logo.
		logger.warning('Channel icon download failed', channel=channel['id'], error=str(exc))
		return

	with open(path, 'wb') as f:
		f.write(response.content)
	channel['icon'] = local_url


async def localize_icons(
	channels: list[dict], client: httpx.AsyncClient, channel_dir: str | None = None
) -> int:
	"""Download missing channel logos into `channel_dir`; rewrite URLs to relative."""
	channel_dir = channel_dir or os.path.join(DIST_DIR, 'channels')
	os.makedirs(channel_dir, exist_ok=True)
	pending = [channel for channel in channels if channel.get('icon')]
	await asyncio.gather(*(_download(client, channel, channel_dir) for channel in pending))
	return sum(1 for channel in channels if not (channel.get('icon') or '').startswith('http'))
