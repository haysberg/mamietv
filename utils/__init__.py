import os

# Source inputs (committed): assets, templates and config.
STATIC_DIR = os.environ.get('MAMIETV_STATIC_DIR', 'static')
TEMPLATES_DIR = os.environ.get('MAMIETV_TEMPLATES_DIR', 'templates')
CONFIG_FILE = os.environ.get('MAMIETV_CONFIG', 'mamietv.toml')

# Output: a self-contained folder ready to publish (GitHub Pages, any static
# host, or `python -m http.server -d dist`). Rebuilt from scratch every run.
DIST_DIR = os.environ.get('MAMIETV_DIST_DIR', 'dist')
