"""ASGI middleware for the pre-compressed static tree.

The generator writes a `.br` and `.gz` sibling next to every file, so on each
request we only have to pick the best sibling the client accepts and hand its
bytes back verbatim. Compression happens once per regeneration, never per
request.
"""

import mimetypes
import os

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import FileResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Remote programme/channel icons come from third-party hosts (programme-tv.net,
# bouygtel...), hence `img-src ... https:`.
_SECURITY_HEADERS = {
	'X-Content-Type-Options': 'nosniff',
	'Referrer-Policy': 'same-origin',
	'X-Frame-Options': 'DENY',
	'Content-Security-Policy': (
		"default-src 'self'; img-src 'self' data: https:; style-src 'self'; "
		"script-src 'self'; connect-src 'self'; base-uri 'self'; "
		"form-action 'self'; object-src 'none'; frame-ancestors 'none'"
	),
	'Cross-Origin-Opener-Policy': 'same-origin',
	'Permissions-Policy': 'interest-cohort=(), browsing-topics=()',
}

# Hashed assets are immutable; HTML/JSON are regenerated, so they get a short TTL.
_IMMUTABLE_EXTENSIONS = {'.css', '.js', '.svg', '.png', '.ico', '.woff2', '.avif'}


def _pick_encoding(accept_encoding: str) -> tuple[str, str]:
	"""Return the (Content-Encoding, suffix) matching the client's preferences."""
	if 'br' in accept_encoding:
		return 'br', '.br'
	if 'gzip' in accept_encoding:
		return 'gzip', '.gz'
	return '', ''


class StaticCompressionMiddleware:
	"""Serve `<path>.br`/`.gz` when present and accepted, else fall through."""

	def __init__(self, app: ASGIApp, directory: str) -> None:
		self.app = app
		self.directory = os.path.abspath(directory)

	async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
		if scope['type'] != 'http' or scope['method'] not in ('GET', 'HEAD'):
			await self.app(scope, receive, send)
			return

		rel = scope['path'].lstrip('/')
		if rel == '' or rel.endswith('/'):
			rel += 'index.html'
		target = os.path.abspath(os.path.join(self.directory, rel))
		# `startswith(dir + sep)` also rejects a path that escapes via `..`.
		if not target.startswith(self.directory + os.sep) or not os.path.isfile(target):
			await self.app(scope, receive, send)
			return

		headers = {'Vary': 'Accept-Encoding'}
		encoding, suffix = _pick_encoding(Headers(scope=scope).get('accept-encoding', ''))
		served = target
		if encoding and os.path.isfile(target + suffix):
			served = target + suffix
			headers['Content-Encoding'] = encoding

		media_type = mimetypes.guess_type(target)[0] or 'application/octet-stream'
		response = FileResponse(served, media_type=media_type, headers=headers)
		await response(scope, receive, send)


class SecurityHeadersMiddleware:
	"""Add security and cache-control headers to every response."""

	def __init__(self, app: ASGIApp) -> None:
		self.app = app

	async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
		if scope['type'] != 'http':
			await self.app(scope, receive, send)
			return

		async def send_wrapper(message: dict) -> None:
			if message['type'] == 'http.response.start':
				headers = MutableHeaders(scope=message)
				for name, value in _SECURITY_HEADERS.items():
					headers[name] = value
				headers.setdefault('Cache-Control', _cache_control(scope['path']))
			await send(message)

		await self.app(scope, receive, send_wrapper)


def _cache_control(path: str) -> str:
	if path == '/healthz':
		return 'no-store'
	# The service worker must be revalidated so updates actually land.
	if path.endswith('/sw.js'):
		return 'no-cache'
	if os.path.splitext(path)[1] in _IMMUTABLE_EXTENSIONS:
		return 'public, max-age=31536000, immutable'
	return 'public, max-age=900'
