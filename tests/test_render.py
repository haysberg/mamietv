import json
import os
import re

from utils import render


def test_copy_assets_creates_a_clean_tree(tmp_path):
	dest = str(tmp_path / 'dist')
	render.copy_assets(dest)

	assert os.path.exists(os.path.join(dest, 'css', 'style.css'))
	assert os.path.exists(os.path.join(dest, 'js', 'app.js'))
	assert os.path.exists(os.path.join(dest, 'manifest.webmanifest'))
	assert os.path.exists(os.path.join(dest, 'sw.js'))
	# Generated output is never carried over from a previous build.
	assert not os.path.exists(os.path.join(dest, 'index.html'))
	assert not os.path.exists(os.path.join(dest, 'data'))


def test_shipped_css_is_minified_without_rewriting_media_queries(tmp_path):
	dest = str(tmp_path / 'dist')
	render.copy_assets(dest)

	with open(os.path.join(dest, 'css', 'style.css'), encoding='utf-8') as f:
		css = f.read()
	assert '\n' not in css.strip()
	# Range syntax (`width<=600px`) is ignored by iOS < 16.4.
	assert '(max-width:600px)' in css


def test_service_worker_is_versioned_with_the_asset_hashes(tmp_path):
	dest = str(tmp_path / 'dist')
	render.copy_assets(dest)
	hashes = render.asset_hashes(dest)

	with open(os.path.join(dest, 'sw.js'), encoding='utf-8') as f:
		sw = f.read()
	assert '__CSS_HASH__' not in sw and '__JS_HASH__' not in sw
	assert f'css/style.css?v={hashes["css_hash"]}' in sw
	assert f'js/app.js?v={hashes["js_hash"]}' in sw


def _epg():
	return {
		'generated_at': '2026-09-20T21:00:00+02:00',
		'day': '2026-09-20',
		'evening_start': '2026-09-20T20:45:00+02:00',
		'evening_end': '2026-09-21T00:00:00+02:00',
		'source': 'https://xmltvfr.fr/xmltv/xmltv_tnt.xml.gz',
		'channels': [
			{
				'id': 'TF1.fr',
				'name': 'TF1',
				'number': 1,
				'icon': 'channels/TF1_fr.png',
				'programs': [
					{
						'start': '2026-09-20T21:10:00+02:00',
						'stop': '2026-09-20T23:15:00+02:00',
						'title': 'Equalizer 3',
						'subtitle': '',
						'desc': 'Un film.',
						'category': 'Film',
					}
				],
			}
		],
	}


def test_write_site_writes_json_and_html(tmp_path):
	dest = str(tmp_path / 'dist')
	render.copy_assets(dest)
	summary = render.write_site(_epg(), dest)

	with open(os.path.join(dest, 'data', 'epg.json'), encoding='utf-8') as f:
		data = json.load(f)
	assert data['channels'][0]['name'] == 'TF1'

	with open(os.path.join(dest, 'data', 'version.json'), encoding='utf-8') as f:
		assert json.load(f) == {'generated_at': '2026-09-20T21:00:00+02:00'}

	with open(os.path.join(dest, 'index.html'), encoding='utf-8') as f:
		html = f.read()
	assert 'MamieTV' in html
	# The list is rendered server-side, so it is present at first paint.
	assert 'channel-head' in html
	assert 'Equalizer 3' in html
	assert '21:10' in html
	assert 'channel-number' in html
	# The update time is shown at the top, spelled out in French.
	assert 'Mis à jour le dimanche 20 septembre à 21 h 00' in html

	assert summary == {'channels': 1, 'programs': 1, 'bytes': summary['bytes']}
	assert summary['bytes'] > 0


def test_descriptions_get_a_hidden_toggle_revealed_by_js(tmp_path):
	dest = str(tmp_path / 'dist')
	render.copy_assets(dest)
	render.write_site(_epg(), dest)

	with open(os.path.join(dest, 'index.html'), encoding='utf-8') as f:
		html = f.read()
	# Whether the text is cut off is measured in the browser, so the button
	# starts hidden and the build does not guess from the length.
	button = re.search(r'<button[^>]*class=more[^>]*>', html).group(0)
	assert {'hidden', 'aria-expanded=false', 'aria-controls=desc-1-1'} <= set(button[8:-1].split())
	assert 'id=desc-1-1' in html
