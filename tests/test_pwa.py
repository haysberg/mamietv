import json
import os

from PIL import Image

from utils import STATIC_DIR


def test_manifest_is_valid_and_icons_exist():
	with open(os.path.join(STATIC_DIR, 'manifest.webmanifest'), encoding='utf-8') as f:
		manifest = json.load(f)

	assert manifest['name']
	assert manifest['short_name']
	assert manifest['start_url']
	assert manifest['display'] == 'standalone'
	assert manifest['theme_color']

	sizes = {icon['sizes'] for icon in manifest['icons']}
	assert {'192x192', '512x512'} <= sizes
	assert any(icon.get('purpose') == 'maskable' for icon in manifest['icons'])
	for icon in manifest['icons']:
		assert os.path.exists(os.path.join(STATIC_DIR, icon['src'])), icon['src']


def test_manifest_screenshots_exist_with_the_declared_sizes():
	with open(os.path.join(STATIC_DIR, 'manifest.webmanifest'), encoding='utf-8') as f:
		manifest = json.load(f)

	factors = {shot.get('form_factor') for shot in manifest['screenshots']}
	assert 'wide' in factors  # needed for the desktop install UI
	assert any(factor != 'wide' for factor in factors)  # and for mobile

	for shot in manifest['screenshots']:
		path = os.path.join(STATIC_DIR, shot['src'])
		with Image.open(path) as image:
			assert f'{image.width}x{image.height}' == shot['sizes'], shot['src']


def test_service_worker_is_committed():
	assert os.path.exists(os.path.join(STATIC_DIR, 'sw.js'))
