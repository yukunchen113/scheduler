import re
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from plex.daily.config_format import (
    SPLITTER,
    TIMEDELTA_FORMAT,
    TIME_FORMAT,
    process_time_to_datetime,
    process_timedelta_to_mins,
)

TIMING_PATTERN = r"\[{0}\](?:\*(?:\d+))?".format(
    TIMEDELTA_FORMAT)

TIMING_DURATION_PATTERN = r"\[({0})\](?:\*(\d+))?".format(
    TIMEDELTA_FORMAT)


TIMING_SET_TIME_PATTERN = r"(?:{0})+(?:(?:.+)\(({1})\))?".format(
    TIMING_PATTERN, TIME_FORMAT)


@dataclass(frozen=True)
class TimingConfig:
    task_description: str
    timings: list[int]
    subtimings: Optional[list["TimingConfig"]] = None
    set_time: Optional[datetime] = None


def process_minutes(input_str: str) -> list[int]:
    matches = re.findall(TIMING_DURATION_PATTERN, input_str)
    tasks = []
    for x, y in matches:
        minutes = process_timedelta_to_mins(x)
        y = y or 1
        tasks += [minutes] * int(y)
    return tasks


def process_set_time(input_str: str) -> Optional[datetime]:
    set_time = re.findall(TIMING_SET_TIME_PATTERN, input_str)
    if not set_time or not set_time[0]:
        return None
    if len(set_time) > 1:
        print(
            f"Invalid set time spec for '{input_str}'. "
            "Skipping setting time. Must only specify one set time.")
        return None
    return process_time_to_datetime(set_time[0])


def get_timing_from_lines(lines: list[str]) -> list[TimingConfig]:
    output: list[TimingConfig] = []
    des, minutes, set_time = None, None, None
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
                output.append(TimingConfig(des, minutes, subtimings, set_time))
            # start accum next timing
            minutes = process_minutes(line)
            set_time = process_set_time(line)
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
        output.append(TimingConfig(des, minutes, subtimings, set_time))
    return output


def get_timing_from_file(filename: str) -> list[TimingConfig]:
    with open(filename) as r:
        lines = r.readlines()
    return get_timing_from_lines(lines)
