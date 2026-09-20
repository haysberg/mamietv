import logging
import os

import structlog

LOGLEVEL = os.getenv('LOGLEVEL', 'INFO').upper()


def configure_logging():
	"""Configure structlog and funnel uvicorn/httpx logs through it."""
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

	formatter = structlog.stdlib.ProcessorFormatter(
		processor=structlog.dev.ConsoleRenderer(colors=True),
		foreign_pre_chain=[
			structlog.stdlib.add_log_level,
			structlog.stdlib.PositionalArgumentsFormatter(),
			structlog.processors.StackInfoRenderer(),
			structlog.processors.TimeStamper(fmt='iso', utc=False),
		],
	)

	handler = logging.StreamHandler()
	handler.setFormatter(formatter)
	logging.basicConfig(handlers=[handler], level=LOGLEVEL)

	structlog_logger = logging.getLogger('structlog')
	structlog_logger.propagate = False

	# Uvicorn and the scheduler should log through the same handler.
	for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access', 'apscheduler'):
		child = logging.getLogger(name)
		child.handlers = [handler]
		child.propagate = False

	logging.getLogger('httpx').setLevel(logging.WARNING)
	logging.getLogger().setLevel(LOGLEVEL)


logger = structlog.get_logger()
