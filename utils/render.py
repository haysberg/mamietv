"""Assemble the publishable `dist/` tree.

`copy_assets()` lays down the committed assets (minifying the shipped JS), then
`write_site()` renders the whole page — channel cards included — into
`index.html` and writes `data/epg.json`. Rendering server-side means the list is
present at first paint (no layout shift), and the page still works without JS.
Writes are atomic (temp file + `os.replace`).
"""

import hashlib
import json
import os
import shutil
from datetime import datetime

import jsmin
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


def _minify_js(dest: str) -> None:
	for root, _dirs, files in os.walk(dest):
		for name in files:
			if not name.endswith('.js'):
				continue
			path = os.path.join(root, name)
			with open(path, encoding='utf-8') as f:
				source = f.read()
			with open(path, 'w', encoding='utf-8') as f:
				f.write(jsmin.jsmin(source))


def copy_assets(dest: str = DIST_DIR) -> None:
	"""Recreate `dest` from a clean, minified copy of the committed `static/`."""
	shutil.rmtree(dest, ignore_errors=True)
	shutil.copytree(STATIC_DIR, dest)
	for name in _GENERATED:
		path = os.path.join(dest, name)
		if os.path.isdir(path):
			shutil.rmtree(path)
		elif os.path.exists(path):
			os.remove(path)
	_minify_js(dest)


def asset_hashes(dest: str = DIST_DIR) -> dict[str, str]:
	"""Content hashes for cache-busting query strings."""
	return {
		'css_hash': _file_hash(os.path.join(dest, 'css', 'style.css')),
		'js_hash': _file_hash(os.path.join(dest, 'js', 'app.js')),
	}


def _view_channels(epg: dict) -> list[dict]:
	"""Turn the JSON model into exactly what the template needs."""
	generated = datetime.fromisoformat(epg['generated_at'])
	cards = []
	for channel in epg['channels']:
		programs = []
		for program in channel['programs']:
			start = datetime.fromisoformat(program['start'])
			stop = datetime.fromisoformat(program['stop'])
			description = program.get('desc') or ''
			programs.append(
				{
					'title': program['title'],
					'subtitle': program.get('subtitle') or '',
					'category': program.get('category') or '',
					'desc': description,
					'start_label': start.strftime('%H:%M'),
					'start_ms': int(start.timestamp() * 1000),
					'stop_ms': int(stop.timestamp() * 1000),
					'ended': stop <= generated,
					'more': len(description) > 140,
				}
			)
		cards.append(
			{
				'name': channel['name'],
				'icon': channel.get('icon'),
				'number': channel.get('number'),
				'programs': programs,
			}
		)
	return cards


def render_index(epg: dict, data_hash: str, dest: str = DIST_DIR) -> str:
	generated = datetime.fromisoformat(epg['generated_at'])
	html = _env.get_template('index.html').render(
		cards=_view_channels(epg),
		data_hash=data_hash,
		generated_at=epg['generated_at'],
		generated_label=generated.strftime('%d/%m/%Y à %H:%M'),
		evening_start=epg['evening_start'],
		evening_end=epg['evening_end'],
		**asset_hashes(dest),
	)
	return minify_html.minify(html, minify_css=False, minify_js=True)


def write_site(epg: dict, dest: str = DIST_DIR) -> dict:
	"""Write `data/epg.json` and the fully rendered `index.html` into `dest`."""
	epg_bytes = json.dumps(epg, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
	_write_atomic(os.path.join(dest, 'data', 'epg.json'), epg_bytes)

	html = render_index(epg, _md5(epg_bytes), dest)
	_write_atomic(os.path.join(dest, 'index.html'), html.encode('utf-8'))

	return {
		'channels': len(epg['channels']),
		'programs': sum(len(channel['programs']) for channel in epg['channels']),
		'bytes': len(html) + len(epg_bytes),
	}
