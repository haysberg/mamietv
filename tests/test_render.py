import json
import os

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

	with open(os.path.join(dest, 'index.html'), encoding='utf-8') as f:
		html = f.read()
	assert 'MamieTV' in html
	# The list is rendered server-side, so it is present at first paint.
	assert 'channel-head' in html
	assert 'Equalizer 3' in html
	assert '21:10' in html
	assert 'channel-number' in html

	assert summary == {'channels': 1, 'programs': 1, 'bytes': summary['bytes']}
	assert summary['bytes'] > 0
