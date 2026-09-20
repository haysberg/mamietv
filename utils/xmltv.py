"""Fetch the XMLTV guide and turn it into the small structure the site serves.

The upstream guide is compressed and lives on another origin, but here the fetch
happens server-side, so neither CORS nor the browser's parsing budget is a
concern: we download once, parse with ElementTree, and hand the front-end a
compact JSON.
"""

import gzip
import re
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import httpx

from utils.config import Config

PARIS = ZoneInfo('Europe/Paris')

# Official French DTT (TNT) channel numbers, shown as a badge on each card.
TNT_NUMBERS = {
	'TF1.fr': 1,
	'France2.fr': 2,
	'France3.fr': 3,
	'France4.fr': 4,
	'France5.fr': 5,
	'M6.fr': 6,
	'Arte.fr': 7,
	'LaChaineParlementaire.fr': 8,
	'W9.fr': 9,
	'TMC.fr': 10,
	'NT1.fr': 11,
	'Gulli.fr': 12,
	'BFMTV.fr': 13,
	'CNews.fr': 14,
	'LCI.fr': 15,
	'FranceInfo.fr': 16,
	'CStar.fr': 17,
	'T18.fr': 18,
	'NOVO19.fr': 19,
	'TF1SeriesFilms.fr': 20,
	'LEquipe21.fr': 21,
	'6ter.fr': 22,
	'Numero23.fr': 23,
	'RMCDecouverte.fr': 24,
	'Cherie25.fr': 25,
}

FETCH_TIMEOUT = 60
CONNECT_TIMEOUT = 10
USER_AGENT = 'MamieTV/1.0 (+https://github.com/haysberg/mamietv)'

# Before this hour, "ce soir" still refers to the previous calendar day.
DAY_RESET_HOUR = 6

# XMLTV timestamps look like "20260919004000 +0200" (seconds and offset are
# sometimes omitted).
_TIME_RE = re.compile(r'^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})?\s*([+-]\d{2}:?\d{2}|Z)?$')

_client: httpx.AsyncClient | None = None
_etag: str | None = None
_modified: str | None = None


def get_client() -> httpx.AsyncClient:
	global _client
	if _client is None:
		_client = httpx.AsyncClient(
			timeout=httpx.Timeout(FETCH_TIMEOUT, connect=CONNECT_TIMEOUT),
			follow_redirects=True,
			headers={'User-Agent': USER_AGENT},
		)
	return _client


async def close_client() -> None:
	"""Close the shared HTTP client, if one was ever opened."""
	global _client
	if _client is not None:
		await _client.aclose()
		_client = None


async def fetch_xml(config: Config) -> bytes | None:
	"""Download the guide, conditionally.

	Returns the (decompressed) XML bytes, or ``None`` when the origin answers
	304 Not Modified and the caller should keep the previous data.
	"""
	global _etag, _modified

	headers = {'User-Agent': config.source.user_agent}
	if _etag:
		headers['If-None-Match'] = _etag
	if _modified:
		headers['If-Modified-Since'] = _modified

	response = await get_client().get(config.source.url, headers=headers)
	if response.status_code == 304:
		return None
	response.raise_for_status()

	_etag = response.headers.get('ETag')
	_modified = response.headers.get('Last-Modified')

	data = response.content
	# The feed is served as a .gz file (Content-Type: application/x-gzip) with
	# no Content-Encoding, so httpx hands back the compressed bytes untouched.
	if data[:2] == b'\x1f\x8b':
		data = gzip.decompress(data)
	return data


def _timezone(offset: str | None):
	"""Turn an XMLTV offset ('+0200', '+02:00', 'Z', absent) into a tzinfo."""
	if not offset:
		# No offset: XMLTV times are Paris wall-clock by convention here.
		return PARIS
	if offset in ('Z', 'z'):
		return timezone.utc
	digits = offset[1:].replace(':', '')
	sign = 1 if offset[0] == '+' else -1
	return timezone(sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:4])))


def parse_xmltv_time(value: str) -> datetime:
	"""Parse an XMLTV timestamp into an aware Europe/Paris datetime.

	The minutes/seconds and the offset are optional, so the digit count is read
	from the regex rather than guessed: `strptime('202609190040 +0200',
	'%Y%m%d%H%M%S %z')` silently succeeds and yields the wrong minute.
	"""
	match = _TIME_RE.match((value or '').strip())
	if not match:
		raise ValueError(f'unparseable XMLTV time: {value!r}')
	year, month, day, hour, minute, second, offset = match.groups()
	parsed = datetime(
		int(year),
		int(month),
		int(day),
		int(hour),
		int(minute),
		int(second or 0),
		tzinfo=_timezone(offset),
	)
	return parsed.astimezone(PARIS)


def evening_window(now: datetime, config: Config) -> tuple[datetime, datetime, str]:
	"""Return the (start, end, day) of the evening containing ``now``.

	``end`` can fall on the next calendar day (18 h -> 1 h). Before
	``DAY_RESET_HOUR`` the evening of the previous day is still the relevant one.
	"""
	local = now.astimezone(PARIS)
	day = local.date()
	if local.hour < DAY_RESET_HOUR:
		day -= timedelta(days=1)

	start = datetime(
		day.year,
		day.month,
		day.day,
		config.evening.start_hour,
		config.evening.start_minute,
		tzinfo=PARIS,
	)
	end_day = (
		day + timedelta(days=1) if config.evening.end_hour <= config.evening.start_hour else day
	)
	end = datetime(
		end_day.year,
		end_day.month,
		end_day.day,
		config.evening.end_hour,
		config.evening.end_minute,
		tzinfo=PARIS,
	)
	return start, end, day.isoformat()


def _text(element: ET.Element | None) -> str:
	return element.text.strip() if element is not None and element.text else ''


def parse_channels(root: ET.Element, only: tuple[str, ...]) -> dict[str, dict]:
	"""Collect <channel> entries, preserving the guide's own (TNT) order."""
	allowed = set(only)
	channels: dict[str, dict] = {}
	for channel in root.findall('channel'):
		cid = channel.get('id')
		if not cid or (allowed and cid not in allowed):
			continue
		icon = channel.find('icon')
		channels[cid] = {
			'id': cid,
			'name': _text(channel.find('display-name')) or cid,
			'number': TNT_NUMBERS.get(cid),
			'icon': icon.get('src') if icon is not None else None,
			'programs': [],
		}
	return channels


def parse_programs(
	root: ET.Element, channels: dict[str, dict], start: datetime, end: datetime
) -> None:
	"""Attach every program whose *start* falls within [start, end]."""
	for programme in root.findall('programme'):
		channel = channels.get(programme.get('channel'))
		if channel is None:
			continue
		try:
			prog_start = parse_xmltv_time(programme.get('start'))
		except ValueError:
			continue
		try:
			prog_stop = parse_xmltv_time(programme.get('stop'))
		except ValueError:
			prog_stop = prog_start + timedelta(hours=1)

		if not (start <= prog_start < end):
			continue

		channel['programs'].append(
			{
				'start': prog_start.isoformat(),
				'stop': prog_stop.isoformat(),
				'title': _text(programme.find('title')) or '(Sans titre)',
				'subtitle': _text(programme.find('sub-title')),
				'desc': _text(programme.find('desc')),
				'category': _text(programme.find('category')),
			}
		)


def _duration_minutes(program: dict) -> float:
	return (
		datetime.fromisoformat(program['stop']) - datetime.fromisoformat(program['start'])
	).total_seconds() / 60


def select_programs(programs: list[dict], limit: int, min_duration_minutes: int) -> list[dict]:
	"""Pick the evening's headliners, Télé-Loisirs style.

	Programs shorter than `min_duration_minutes` (weather, fillers, trailers) are
	ignored when choosing, so TF1 surfaces "Equalizer 3" and "Spider-Man" rather
	than a stack of five-minute interludes. When nothing clears the bar we fall
	back to the first programs so a channel is never left empty.
	"""
	if limit <= 0:
		return programs
	significant = [p for p in programs if _duration_minutes(p) >= min_duration_minutes]
	return (significant or programs)[:limit]


def build_epg(xml_bytes: bytes, config: Config, now: datetime) -> dict:
	"""Parse the guide into the JSON structure served to the front-end."""
	start, end, day = evening_window(now, config)
	buffer = timedelta(hours=config.evening.buffer_hours)

	root = ET.fromstring(xml_bytes)
	channels = parse_channels(root, config.evening.channels)
	parse_programs(root, channels, start - buffer, end + buffer)

	served = []
	for channel in channels.values():
		if not channel['programs']:
			continue
		channel['programs'].sort(key=lambda program: program['start'])
		channel['programs'] = select_programs(
			channel['programs'],
			config.evening.max_programs,
			config.evening.min_duration_minutes,
		)
		served.append(channel)

	# Display in channel-number order (unknown numbers last).
	served.sort(key=lambda channel: (channel['number'] is None, channel['number'] or 0))

	return {
		'generated_at': now.astimezone(PARIS).isoformat(),
		'day': day,
		'evening_start': start.isoformat(),
		'evening_end': end.isoformat(),
		'source': config.source.url,
		'channels': served,
	}
