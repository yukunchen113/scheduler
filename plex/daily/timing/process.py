import copy
import dataclasses
import re
from datetime import datetime
from typing import Optional

from plex.daily.config_format import (
    SPLITTER,
    TIME_FORMAT,
    TIMEDELTA_FORMAT,
    process_mins_to_timedelta,
    process_time_to_datetime,
    process_timedelta_to_mins,
)
from plex.daily.timing.base import (
    SetTime,
    TimingConfig,
    pack_timing_uuid,
    unpack_timing_uuid,
)
from plex.daily.unique_id import PATTERN_UUID, make_random_uuid

TIMING_PATTERN = r"\[{0}\](?:\*(?:\d+))?".format(TIMEDELTA_FORMAT)

TIMING_DURATION_PATTERN = r"\[({0})\](?:\*(\d+))?".format(TIMEDELTA_FORMAT)

TIMING_SET_TIME_PATTERN = r"(?:{0})+(?:(?:.+)\(({1})(s|e|S|E)?\))?".format(
    TIMING_PATTERN, TIME_FORMAT
)

TIMING_UNIQUE_RETRIES = 100
TIMING_UUID_LENGTH = 4


def convert_timing_to_str(timing: TimingConfig, *, n_indents: Optional[int] = None):
    string = f"{timing.task_description} |{timing.uuid}| "  # add description + uuid
    timing_spec = ""
    for tset in timing.raw_timings:
        if tset:
            timing_spec += f"[{process_mins_to_timedelta(tset[0])}]"
            if len(tset) > 1:
                timing_spec += f"*{len(tset)}"
    string += timing_spec
    if timing.set_time:
        time_format = f" ({int(timing.set_time.datetime.strftime('%I'))}"
        if timing.set_time.datetime.minute:
            time_format += ":%M"
        time_format += "%p"
        if not timing.set_time.is_start:
            time_format += "e"
        time_format += ")"
        string += timing.set_time.datetime.strftime(time_format).lower()
    string += timing.end_line  # add end line information

    if n_indents is None:
        n_indents = timing.subtiming_level

    return indent_line(string, n_indents=n_indents)


def process_minutes(input_str: str) -> list[int]:
    matches = re.findall(TIMING_DURATION_PATTERN, input_str)
    tasks = []
    for x, y in matches:
        minutes = process_timedelta_to_mins(x)
        y = y or 1
        tasks.append([minutes] * int(y))
    return tasks


def is_valid_timing_str(string: str):
    return re.findall(TIMING_DURATION_PATTERN, string)


def process_set_time(
    input_str: str, config_date: Optional[datetime]
) -> Optional[SetTime]:
    set_time = re.findall(TIMING_SET_TIME_PATTERN, input_str)
    if not set_time or not set_time[0][0]:
        return None
    if len(set_time) > 1:
        print(
            f"Invalid set time spec for '{input_str}'. "
            "Skipping setting time. Must only specify one set time."
        )
        return None
    return SetTime(
        process_time_to_datetime(set_time[0][0], config_date),
        set_time[0][1] not in ["E", "e"],
    )


def process_information_after_timing(input_str: str):
    output = re.split(TIMING_SET_TIME_PATTERN, input_str)
    return output[-1]


def indent_line(string: str, n_indents: int = 1):
    for _ in range(n_indents):
        if not re.match(r"\t*-", string):
            if not string.startswith(" "):
                string = " " + string
            string = "-" + string
        else:
            string = "\t" + string
    return string


def split_desc_and_uuid(description: str, used_uuids: set = None):
    if used_uuids is None:
        used_uuids = set()
    id_from_desc = re.findall(rf"\|((?:{PATTERN_UUID})+)\|", description)
    if id_from_desc:
        # get from raw description
        timing_uuid = id_from_desc[0]
    else:
        # set random timing_uuid
        timing_uuid = make_random_uuid(TIMING_UUID_LENGTH)
        for _ in range(100):
            if timing_uuid not in used_uuids:
                break
            timing_uuid = make_random_uuid(TIMING_UUID_LENGTH)
        else:
            raise ValueError(
                f"Unable to generate unique uuid after {TIMING_UNIQUE_RETRIES} tries"
            )
    used_uuids.add(timing_uuid)

    timing_description = re.findall(
        rf"([^\|]+)(?:\|(?:{PATTERN_UUID})+\|)?", description
    )[0].strip()
    return timing_description, timing_uuid


def get_timing_from_lines(
    lines: list[str],
    config_date: Optional[datetime] = None,
    existing_uuids: Optional[set[str]] = None,
) -> tuple[list[TimingConfig], list[str]]:
    """gets the timing from lines

    Args:
        lines (list[str]): lines that contains timings
        config_date (Optional[datetime], optional): date for the timings. Defaults to None.

    Returns:
        tuple[list[TimingConfig], list[str]]: list of timings, list of new timing lines (after some post processing)
    """
    if existing_uuids is None:
        existing_uuids = gather_existing_uuids_from_lines(lines)
    output, replaced = get_timing_from_indexed_lines(
        dict(enumerate(lines)), config_date, existing_uuids
    )
    return output, [line for _, line in sorted(replaced.items())]


def gather_existing_uuids_from_lines(lines):
    uuids = set()
    for line in lines:
        if is_valid_timing_str(line):
            split_desc_and_uuid(
                line.split("[")[0].strip(), used_uuids=uuids
            )  # updates uuids in place
    return uuids


def get_timing_from_indexed_lines(
    lines: dict[int, str],
    config_date: Optional[datetime] = None,
    used_uuids: set[str] = set(),
    subtiming_level: int = 0,
) -> tuple[list[TimingConfig], dict[int, str]]:
    output: list[TimingConfig] = []

    timing_config = None
    subtiming_lines: Optional[dict[int, str]] = None
    replaced_lines = copy.copy(lines)

    for lidx, line in sorted(lines.items()):
        if line.startswith(SPLITTER):
            # splitter
            break
        elif re.match(r"(?:\t+)?-\s.*", line):
            if subtiming_lines is None:
                subtiming_lines = {}
            subtiming_lines[lidx] = line[1:]
        else:
            # construct prev timing
            if timing_config is not None:
                if subtiming_lines:
                    subtimings, replaced_sublines = get_timing_from_indexed_lines(
                        subtiming_lines,
                        config_date,
                        used_uuids=used_uuids,
                        subtiming_level=subtiming_level + 1,
                    )
                    replaced_lines.update(
                        {k: indent_line(v) for k, v in replaced_sublines.items()}
                    )
                else:
                    subtimings = None
                output.append(
                    dataclasses.replace(timing_config, subtimings=subtimings or [])
                )

            # start accum next timing
            if is_valid_timing_str(line):
                subtiming_lines = None
                process_information_after_timing(line)
                tim_des, tim_uuid = split_desc_and_uuid(
                    line.split("[")[0].strip(), used_uuids
                )
                timing_config = TimingConfig(
                    task_description=tim_des,
                    raw_timings=process_minutes(line),
                    subtimings=[],
                    set_time=process_set_time(line, config_date),
                    uuid=tim_uuid,
                    end_line=process_information_after_timing(line),
                    subtiming_level=subtiming_level,
                )
                replaced_lines[lidx] = convert_timing_to_str(timing_config, n_indents=0)
            else:
                timing_config = None

    # construct last timing
    if timing_config is not None:
        if subtiming_lines:
            subtimings, replaced_sublines = get_timing_from_indexed_lines(
                subtiming_lines,
                config_date,
                used_uuids=used_uuids,
                subtiming_level=subtiming_level + 1,
            )
            replaced_lines.update(
                {k: indent_line(v) for k, v in replaced_sublines.items()}
            )
        else:
            subtimings = None
        output.append(dataclasses.replace(timing_config, subtimings=subtimings or []))
    return output, replaced_lines
