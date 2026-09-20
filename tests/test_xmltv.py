from datetime import datetime

import pytest

from utils.config import Config, EveningConfig, SourceConfig
from utils.xmltv import PARIS, build_epg, evening_window, parse_xmltv_time, select_programs

SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="TF1.fr"><display-name>TF1</display-name><icon src="http://x/tf1.png"/></channel>
  <channel id="M6.fr"><display-name>M6</display-name></channel>
  <programme start="20260920190000 +0200" stop="20260920210000 +0200" channel="TF1.fr">
    <title lang="fr">Journal</title><desc lang="fr">Les infos.</desc>
    <category lang="fr">Information</category>
  </programme>
  <programme start="20260920210000 +0200" stop="20260920230500 +0200" channel="TF1.fr">
    <title>Film du soir</title>
  </programme>
  <programme start="20260920100000 +0200" stop="20260920110000 +0200" channel="TF1.fr">
    <title>Matin</title>
  </programme>
  <programme start="20260920200000 +0200" stop="20260920220000 +0200" channel="M6.fr">
    <title>M6 Show</title>
  </programme>
</tv>
"""


def _config(channels=(), buffer_hours=1):
	return Config(
		source=SourceConfig(url='http://example.test/guide.xml.gz'),
		evening=EveningConfig(
			start_hour=18, end_hour=1, buffer_hours=buffer_hours, channels=channels
		),
	)


@pytest.mark.parametrize(
	('raw', 'expected'),
	[
		('20260919004000 +0200', datetime(2026, 9, 19, 0, 40, tzinfo=PARIS)),
		('202609190040 +0200', datetime(2026, 9, 19, 0, 40, tzinfo=PARIS)),
		('20260919004000', datetime(2026, 9, 19, 0, 40, tzinfo=PARIS)),
	],
)
def test_parse_xmltv_time(raw, expected):
	assert parse_xmltv_time(raw) == expected


def test_parse_xmltv_time_rejects_garbage():
	with pytest.raises(ValueError):
		parse_xmltv_time('not-a-date')


def test_evening_window_evening():
	start, end, day = evening_window(datetime(2026, 9, 20, 12, 0, tzinfo=PARIS), _config())
	assert day == '2026-09-20'
	assert start == datetime(2026, 9, 20, 18, 0, tzinfo=PARIS)
	assert end == datetime(2026, 9, 21, 1, 0, tzinfo=PARIS)


def test_evening_window_after_midnight_uses_previous_day():
	start, end, day = evening_window(datetime(2026, 9, 21, 2, 0, tzinfo=PARIS), _config())
	assert day == '2026-09-20'
	assert start == datetime(2026, 9, 20, 18, 0, tzinfo=PARIS)
	assert end == datetime(2026, 9, 21, 1, 0, tzinfo=PARIS)


def test_evening_window_supports_minutes():
	config = Config(
		source=SourceConfig(url='http://example.test/guide.xml.gz'),
		evening=EveningConfig(start_hour=20, start_minute=45, end_hour=0, end_minute=0),
	)
	start, end, day = evening_window(datetime(2026, 9, 20, 12, 0, tzinfo=PARIS), config)
	assert day == '2026-09-20'
	assert start == datetime(2026, 9, 20, 20, 45, tzinfo=PARIS)
	assert end == datetime(2026, 9, 21, 0, 0, tzinfo=PARIS)


def test_build_epg_filters_to_evening_and_keeps_order():
	epg = build_epg(SAMPLE, _config(), datetime(2026, 9, 20, 12, 0, tzinfo=PARIS))

	assert epg['day'] == '2026-09-20'
	assert [channel['id'] for channel in epg['channels']] == ['TF1.fr', 'M6.fr']

	tf1 = epg['channels'][0]
	titles = [program['title'] for program in tf1['programs']]
	assert titles == ['Journal', 'Film du soir']
	assert tf1['programs'][0]['category'] == 'Information'
	assert tf1['icon'] == 'http://x/tf1.png'
	assert tf1['number'] == 1

	assert [p['title'] for p in epg['channels'][1]['programs']] == ['M6 Show']
	assert epg['channels'][1]['number'] == 6


def test_build_epg_respects_channel_whitelist():
	epg = build_epg(
		SAMPLE, _config(channels=('M6.fr',)), datetime(2026, 9, 20, 12, 0, tzinfo=PARIS)
	)
	assert [channel['id'] for channel in epg['channels']] == ['M6.fr']


def test_build_epg_drops_programs_starting_before_the_window():
	straddling = SAMPLE.replace(
		b'start="20260920100000 +0200" stop="20260920110000 +0200"',
		b'start="20260920173000 +0200" stop="20260920183000 +0200"',
	)
	epg = build_epg(straddling, _config(buffer_hours=0), datetime(2026, 9, 20, 12, 0, tzinfo=PARIS))
	titles = [program['title'] for program in epg['channels'][0]['programs']]
	assert 'Matin' not in titles


def _program(start, stop, title):
	# A stop earlier than the start means the show runs past midnight.
	stop_day = '21' if stop <= start else '20'
	return {
		'start': f'2026-09-20T{start}:00+02:00',
		'stop': f'2026-09-{stop_day}T{stop}:00+02:00',
		'title': title,
	}


def test_select_programs_skips_short_interstitials():
	programs = [
		_program('20:45', '20:50', 'Météo'),
		_program('20:50', '20:55', 'Bande-annonce'),
		_program('21:10', '23:15', 'Film'),
		_program('23:15', '01:45', 'Série'),
	]
	titles = [p['title'] for p in select_programs(programs, 2, 25)]
	assert titles == ['Film', 'Série']


def test_select_programs_falls_back_when_all_are_short():
	programs = [_program('20:45', '20:50', 'A'), _program('20:50', '20:55', 'B')]
	assert [p['title'] for p in select_programs(programs, 2, 25)] == ['A', 'B']


def test_select_programs_zero_means_keep_everything():
	programs = [_program('20:45', '20:50', 'A'), _program('21:10', '23:15', 'Film')]
	assert select_programs(programs, 0, 25) == programs
