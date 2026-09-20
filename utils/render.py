"""Assemble the publishable `dist/` tree.

`copy_assets()` lays down the committed assets, then `write_site()` adds the
generated `data/epg.json` and `index.html`. Writes are atomic (temp file +
`os.replace`) so a preview served mid-build never sees a half-written file.
"""

import hashlib
import json
import os
import shutil

import minify_html
from jinja2 import Environment, FileSystemLoader, select_autoescape

from utils import DIST_DIR, STATIC_DIR, TEMPLATES_DIR

# Generated directories/files that must never be copied from `static/` even if
# a previous run left them there.
_GENERATED = ('data', 'channels', 'index.html', 'index.html.br', 'index.html.gz')

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


def _write_atomic(path: str, data: bytes) -> None:
	os.makedirs(os.path.dirname(path), exist_ok=True)
	tmp = path + '.tmp'
	with open(tmp, 'wb') as f:
		f.write(data)
	os.replace(tmp, path)


def copy_assets(dest: str = DIST_DIR) -> None:
	"""Recreate `dest` from a clean copy of the committed `static/` tree."""
	shutil.rmtree(dest, ignore_errors=True)
	shutil.copytree(STATIC_DIR, dest)
	for name in _GENERATED:
		path = os.path.join(dest, name)
		if os.path.isdir(path):
			shutil.rmtree(path)
		elif os.path.exists(path):
			os.remove(path)


def asset_hashes(dest: str = DIST_DIR) -> dict[str, str]:
	"""Content hashes for cache-busting query strings."""
	return {
		'css_hash': _file_hash(os.path.join(dest, 'css', 'style.css')),
		'js_hash': _file_hash(os.path.join(dest, 'js', 'app.js')),
	}


def render_index(epg: dict, data_hash: str, dest: str = DIST_DIR) -> str:
	html = _env.get_template('index.html').render(
		data_hash=data_hash,
		generated_at=epg['generated_at'],
		source=epg['source'],
		**asset_hashes(dest),
	)
	return minify_html.minify(html, minify_css=False, minify_js=True)


def write_site(epg: dict, dest: str = DIST_DIR) -> dict:
	"""Write `data/epg.json` and `index.html` into `dest`."""
	epg_bytes = json.dumps(epg, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
	_write_atomic(os.path.join(dest, 'data', 'epg.json'), epg_bytes)

	html = render_index(epg, _md5(epg_bytes), dest)
	_write_atomic(os.path.join(dest, 'index.html'), html.encode('utf-8'))

	return {
		'channels': len(epg['channels']),
		'programs': sum(len(channel['programs']) for channel in epg['channels']),
		'bytes': len(html) + len(epg_bytes),
	}
