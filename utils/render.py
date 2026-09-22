"""Assemble the publishable `dist/` tree.

`copy_assets()` lays down the committed assets (minifying the shipped JS, CSS and HTML), then
`write_site()` renders the whole page — channel cards included — into
`index.html` and writes `data/epg.json` plus the tiny `data/version.json` the
page polls to spot a newer guide. Rendering server-side means the list is
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
import rcssmin
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


# rcssmin only strips whitespace and comments. minify-html's CSS mode would also
# rewrite `(max-width: 600px)` into `(width<=600px)`, which iOS < 16.4 ignores.
_MINIFIERS = {
	'.js': jsmin.jsmin,
	'.css': rcssmin.cssmin,
	'.html': lambda source: minify_html.minify(source, minify_css=False, minify_js=True),
}


def _minify_assets(dest: str) -> None:
	for root, _dirs, files in os.walk(dest):
		for name in files:
			minify = _MINIFIERS.get(os.path.splitext(name)[1])
			if minify is None:
				continue
			path = os.path.join(root, name)
			with open(path, encoding='utf-8') as f:
				source = f.read()
			with open(path, 'w', encoding='utf-8') as f:
				f.write(minify(source))


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
	_minify_assets(dest)
	_stamp_service_worker(dest)


def _stamp_service_worker(dest: str) -> None:
	"""Version the service worker's cache and precache list with the asset hashes."""
	path = os.path.join(dest, 'sw.js')
	hashes = asset_hashes(dest)
	with open(path, encoding='utf-8') as f:
		source = f.read()
	source = source.replace('__CSS_HASH__', hashes['css_hash'])
	source = source.replace('__JS_HASH__', hashes['js_hash'])
	_write_atomic(path, source.encode('utf-8'))


def asset_hashes(dest: str = DIST_DIR) -> dict[str, str]:
	"""Content hashes for cache-busting query strings."""
	return {
		'css_hash': _file_hash(os.path.join(dest, 'css', 'style.css')),
		'js_hash': _file_hash(os.path.join(dest, 'js', 'app.js')),
	}


_WEEKDAYS = ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche')
_MONTHS = (
	'janvier',
	'février',
	'mars',
	'avril',
	'mai',
	'juin',
	'juillet',
	'août',
	'septembre',
	'octobre',
	'novembre',
	'décembre',
)


def _french_datetime(value: datetime) -> str:
	"""'dimanche 20 septembre à 21 h 11', without depending on the system locale."""
	day = _WEEKDAYS[value.weekday()]
	month = _MONTHS[value.month - 1]
	return f'{day} {value.day} {month} à {value.hour} h {value.minute:02d}'


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


def render_index(epg: dict, dest: str = DIST_DIR) -> str:
	generated = datetime.fromisoformat(epg['generated_at'])
	html = _env.get_template('index.html').render(
		cards=_view_channels(epg),
		generated_at=epg['generated_at'],
		generated_label=_french_datetime(generated),
		evening_start=epg['evening_start'],
		evening_end=epg['evening_end'],
		**asset_hashes(dest),
	)
	return minify_html.minify(html, minify_css=False, minify_js=True)


def write_site(epg: dict, dest: str = DIST_DIR) -> dict:
	"""Write the guide JSON files and the fully rendered `index.html` into `dest`."""
	epg_bytes = json.dumps(epg, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
	_write_atomic(os.path.join(dest, 'data', 'epg.json'), epg_bytes)
	# A few dozen bytes instead of the whole guide for the periodic check.
	version = json.dumps({'generated_at': epg['generated_at']}).encode('utf-8')
	_write_atomic(os.path.join(dest, 'data', 'version.json'), version)

	html = render_index(epg, dest)
	_write_atomic(os.path.join(dest, 'index.html'), html.encode('utf-8'))

	return {
		'channels': len(epg['channels']),
		'programs': sum(len(channel['programs']) for channel in epg['channels']),
		'bytes': len(html) + len(epg_bytes),
	}
