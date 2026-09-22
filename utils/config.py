"""Typed view of `mamietv.toml`.

Kept deliberately tiny: the whole config is a handful of scalars, so dataclasses
beat a settings library and keep the parsing obvious and testable.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SourceConfig:
	url: str


@dataclass(frozen=True)
class EveningConfig:
	# "Ce soir" window, in Paris wall-clock time. end_hour may be smaller than
	# start_hour (e.g. 20 -> 0) and then refers to the following day.
	start_hour: int = 20
	start_minute: int = 0
	end_hour: int = 0
	end_minute: int = 0
	# A show that began before the window is kept when at least this many
	# minutes of it remain at the window start (a match kicking off at 20:35).
	carry_over_minutes: int = 30
	# Télé-Loisirs-style selection: keep at most `max_programs` "real" shows per
	# channel (the headliner and its follow-up). Shows shorter than
	# `min_duration_minutes` (weather, fillers) are ignored when choosing.
	max_programs: int = 2
	min_duration_minutes: int = 25
	# Empty means "every channel present in the guide".
	channels: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Config:
	source: SourceConfig
	evening: EveningConfig = field(default_factory=EveningConfig)


def load_config(path: str | Path) -> Config:
	with open(path, 'rb') as f:
		raw = tomllib.load(f)

	source = SourceConfig(**raw.get('source', {}))
	evening_raw = raw.get('evening', {})
	evening = EveningConfig(
		start_hour=evening_raw.get('start_hour', 20),
		start_minute=evening_raw.get('start_minute', 0),
		end_hour=evening_raw.get('end_hour', 0),
		end_minute=evening_raw.get('end_minute', 0),
		carry_over_minutes=evening_raw.get('carry_over_minutes', 30),
		max_programs=evening_raw.get('max_programs', 2),
		min_duration_minutes=evening_raw.get('min_duration_minutes', 25),
		channels=tuple(evening_raw.get('channels', ())),
	)
	return Config(source=source, evening=evening)
