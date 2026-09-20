import os

# Paths are overridable so the app can run from a container or a systemd unit
# with its data outside the source tree, without assuming the current directory.
STATIC_DIR = os.environ.get('MAMIETV_STATIC_DIR', 'static')
TEMPLATES_DIR = os.environ.get('MAMIETV_TEMPLATES_DIR', 'templates')
CONFIG_FILE = os.environ.get('MAMIETV_CONFIG', 'mamietv.toml')

DATA_DIR = os.path.join(STATIC_DIR, 'data')
INDEX_FILE = os.path.join(STATIC_DIR, 'index.html')
EPG_FILE = os.path.join(DATA_DIR, 'epg.json')

# The runtime generator writes here; make sure the tree exists before the
# scheduler and the static middleware touch it.
os.makedirs(DATA_DIR, exist_ok=True)
