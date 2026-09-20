"""Render the site's HTML/JSON and write the pre-compressed static tree.

Rendering is intentionally synchronous and CPU-bound (brotli quality 11,
minify-html): the scheduler calls it through ``asyncio.to_thread`` so the event
loop keeps serving requests while a regeneration runs.
"""

import hashlib
import json
import os

import minify_html
from jinja2 import Environment, FileSystemLoader, select_autoescape

from precompress import write_compressed
from utils import DATA_DIR, INDEX_FILE, STATIC_DIR, TEMPLATES_DIR

# Text assets that get a `.br`/`.gz` sibling at startup. Raster images
# (channel logos) are already compressed, so compressing them again would only
# waste CPU. Generated files (index.html, data/*.json) go through write_site.
_ASSET_EXTENSIONS = {'.css', '.js', '.svg', '.txt', '.webmanifest'}

_env = Environment(
	loader=FileSystemLoader(TEMPLATES_DIR),
	autoescape=select_autoescape(['html']),
	trim_blocks=True,
	lstrip_blocks=True,
)


def _md5(data: bytes) -> str:
	return hashlib.md5(data).hexdigest()[:8]


def _file_hash(path: str) -> str:
	with open(path, 'rb') as f:
		return _md5(f.read())


def asset_hashes() -> dict[str, str]:
	"""Content hashes for cache-busting query strings on the static assets."""
	return {
		'css_hash': _file_hash(os.path.join(STATIC_DIR, 'css', 'style.css')),
		'js_hash': _file_hash(os.path.join(STATIC_DIR, 'js', 'app.js')),
	}


def render_index(epg: dict, data_hash: str) -> str:
	html = _env.get_template('index.html').render(
		data_hash=data_hash,
		generated_at=epg['generated_at'],
		source=epg['source'],
		**asset_hashes(),
	)
	# CSS/JS is already minified at the source; only inline markup is squeezed.
	return minify_html.minify(html, minify_css=False, minify_js=True)


def write_site(epg: dict) -> dict:
	"""Write index.html and data/epg.json (plus .br/.gz) and return a summary."""
	epg_bytes = json.dumps(epg, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
	write_compressed(os.path.join(DATA_DIR, 'epg.json'), epg_bytes)

	html = render_index(epg, _md5(epg_bytes))
	write_compressed(INDEX_FILE, html)

	return {
		'channels': len(epg['channels']),
		'programs': sum(len(channel['programs']) for channel in epg['channels']),
		'bytes': len(html) + len(epg_bytes),
	}


def precompress_assets() -> int:
	"""Create missing `.br`/`.gz` siblings for the committed static assets.

	Only missing siblings are produced, so restarting the app does not re-brotli
	the whole tree at quality 11. Source files themselves are never touched.
	"""
	count = 0
	for root, _dirs, files in os.walk(STATIC_DIR):
		if os.path.abspath(root) == os.path.abspath(DATA_DIR):
			continue
		for name in files:
			if name.endswith(('.br', '.gz', '.tmp')):
				continue
			if os.path.splitext(name)[1] not in _ASSET_EXTENSIONS:
				continue
			path = os.path.join(root, name)
			if os.path.exists(path + '.br') and os.path.exists(path + '.gz'):
				continue
			with open(path, 'rb') as f:
				write_compressed(path, f.read())
			count += 1
	return count
