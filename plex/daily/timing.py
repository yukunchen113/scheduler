import re
from dataclasses import dataclass
from typing import Optional

from plex.daily.config_format import (
    SPLITTER,
    TIMEDELTA_FORMAT,
    process_timedelta_to_mins,
)


@dataclass(frozen=True)
class TimingConfig:
    task_description: str
    timings: list[int]
    subtimings: Optional[list["TimingConfig"]] = None


def process_minutes(input_str: str) -> list[int]:
    pattern = r"\[({})\](?:\*(\d+))?".format(TIMEDELTA_FORMAT)
    matches = re.findall(pattern, input_str)
    tasks = []
    for x, y in matches:
        minutes = process_timedelta_to_mins(x)
        y = y or 1
        tasks += [minutes] * int(y)
    return tasks


def get_timing_from_lines(lines: list[str]) -> list[TimingConfig]:
    output: list[TimingConfig] = []
    des, minutes = None, None
    subtiming_lines: Optional[list[str]] = None
    for line in lines:
        if line.startswith(SPLITTER):
            # splitter
            break
        elif re.match(r"(?:\t+)?-.*\n", line):
            if subtiming_lines is None:
                subtiming_lines = []
            subtiming_lines.append(line[1:])
        else:
            # construct last timing
            if des is not None and minutes is not None:
                if subtiming_lines:
                    subtimings = get_timing_from_lines(subtiming_lines)
                else:
                    subtimings = None
                output.append(TimingConfig(des, minutes, subtimings))
            # start accum next timing
            minutes = process_minutes(line)
            if not minutes:
                continue
            des = line.split("[")[0].strip()
            subtiming_lines = None
            # construct last timing
    if des is not None and minutes is not None:
        if subtiming_lines:
            subtimings = get_timing_from_lines(subtiming_lines)
        else:
            subtimings = None
        output.append(TimingConfig(des, minutes, subtimings))
    return output


def get_timing_from_file(filename: str) -> list[TimingConfig]:
    with open(filename) as r:
        lines = r.readlines()
    return get_timing_from_lines(lines)
