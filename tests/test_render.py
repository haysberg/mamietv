import os

from precompress import write_compressed
from utils import render


def test_write_compressed_writes_plain_and_siblings(tmp_path):
	path = os.path.join(tmp_path, 'index.html')
	write_compressed(path, '<p>bonjour</p>')

	with open(path, 'rb') as f:
		plain = f.read()
	assert plain == b'<p>bonjour</p>'
	assert os.path.exists(path + '.br')
	assert os.path.exists(path + '.gz')
	assert os.path.getsize(path + '.gz') > 0


def _touch(path, data):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, 'wb') as f:
		f.write(data)


def test_precompress_assets_only_touches_missing_siblings(tmp_path, monkeypatch):
	static = tmp_path / 'static'
	data = static / 'data'
	data.mkdir(parents=True)

	_touch(str(static / 'css' / 'style.css'), b'body{color:red}')
	_touch(str(static / 'js' / 'app.js'), b'console.log(1)')
	# Generated data must be ignored: it is compressed by write_site.
	_touch(str(data / 'epg.json'), b'{}')
	# Raster images are already compressed and must be left alone.
	_touch(str(static / 'channels' / 'TF1_fr.png'), b'\x89PNG\r\n')
	# A file that already has its siblings must not be processed.
	_touch(str(static / 'robots.txt'), b'ok')
	_touch(str(static / 'robots.txt.br'), b'ok')
	_touch(str(static / 'robots.txt.gz'), b'ok')

	monkeypatch.setattr(render, 'STATIC_DIR', str(static))
	monkeypatch.setattr(render, 'DATA_DIR', str(data))

	count = render.precompress_assets()

	assert count == 2  # style.css and app.js
	assert os.path.exists(str(static / 'css' / 'style.css.br'))
	assert os.path.exists(str(static / 'js' / 'app.js.gz'))
	assert not os.path.exists(str(data / 'epg.json.br'))
	assert not os.path.exists(str(static / 'channels' / 'TF1_fr.png.br'))
