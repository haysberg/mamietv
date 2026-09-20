import logging
import os

import structlog

LOGLEVEL = os.getenv('LOGLEVEL', 'INFO').upper()


def configure_logging() -> None:
	"""Configure structlog with a readable console renderer."""
	processors = [
		structlog.stdlib.PositionalArgumentsFormatter(),
		structlog.processors.StackInfoRenderer(),
		structlog.dev.ConsoleRenderer(colors=True),
	]

	structlog.configure(
		processors=processors,
		wrapper_class=structlog.make_filtering_bound_logger(LOGLEVEL),
		context_class=dict,
		logger_factory=structlog.stdlib.LoggerFactory(),
		cache_logger_on_first_use=True,
	)

	handler = logging.StreamHandler()
	handler.setFormatter(
		structlog.stdlib.ProcessorFormatter(
			processor=structlog.dev.ConsoleRenderer(colors=True),
			foreign_pre_chain=[
				structlog.stdlib.add_log_level,
				structlog.stdlib.PositionalArgumentsFormatter(),
				structlog.processors.TimeStamper(fmt='iso', utc=False),
			],
		)
	)
	logging.basicConfig(handlers=[handler], level=LOGLEVEL)
	logging.getLogger('httpx').setLevel(logging.WARNING)


logger = structlog.get_logger()
