"""Generate the static site once and exit.

This is what CI (and `task build`) runs: fetch the guide, download the logos,
render `static/index.html` and `static/data/epg.json`. The FastAPI app in
`app.py` reuses the exact same `init_service()` for its scheduled refreshes.
"""

import asyncio

from utils.logs import configure_logging
from utils.utils import init_service


def main() -> None:
	configure_logging()
	asyncio.run(init_service())


if __name__ == '__main__':
	main()
