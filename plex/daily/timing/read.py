from typing import Optional
from datetime import datetime
from plex.daily.timing.base import TimingConfig
from plex.daily.timing.process import get_timing_from_lines
from plex.daily.config_format import SPLITTER


def get_all_timing_lines(all_lines: list[str]) -> list[str]:
    lines = []
    for line in all_lines:
        if line.startswith(SPLITTER):
            # splitter
            break
        lines.append(line)
    return lines


def get_timing_from_file(
    filename: str, config_date: Optional[datetime] = None, ignore_future: bool = False
) -> list[TimingConfig]:
    with open(filename) as r:
        lines = get_all_timing_lines(r.readlines())
    return get_timing_from_lines(lines, config_date)
