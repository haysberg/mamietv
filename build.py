"""Generate the static site into `dist/`.

    uv run python build.py

The output is a self-contained folder (HTML/CSS/JS + data + icons) that can be
published anywhere, GitHub Pages included.
"""

import asyncio

from utils.build import build
from utils.logs import configure_logging


def main() -> None:
	configure_logging()
	asyncio.run(build())


if __name__ == '__main__':
	main()
