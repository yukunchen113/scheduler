import re
from typing import Optional
import copy
from datetime import datetime
from plex.daily.timing.base import TimingConfig, SetTime
from plex.daily.unique_id import PATTERN_UUID, make_random_uuid
from plex.daily.config_format import (
    SPLITTER,
    process_time_to_datetime,
    process_timedelta_to_mins,
)
from plex.daily.config_format import (
    TIMEDELTA_FORMAT,
    TIME_FORMAT,
)

TIMING_PATTERN = r"\[{0}\](?:\*(?:\d+))?".format(TIMEDELTA_FORMAT)

TIMING_DURATION_PATTERN = r"\[({0})\](?:\*(\d+))?".format(TIMEDELTA_FORMAT)

TIMING_SET_TIME_PATTERN = r"(?:{0})+(?:(?:.+)\(({1})(s|e|S|E)?\))?".format(
    TIMING_PATTERN, TIME_FORMAT
)


def process_minutes(input_str: str) -> list[int]:
    matches = re.findall(TIMING_DURATION_PATTERN, input_str)
    tasks = []
    for x, y in matches:
        minutes = process_timedelta_to_mins(x)
        y = y or 1
        tasks += [minutes] * int(y)
    return tasks


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
    
def indent_line(string):
    if not string.startswith("-"):
        return "-" + string
    return "\t" + string

def split_desc_and_uuid(raw_description: str):
    id_from_desc = re.findall(
        rf"\|((?:{PATTERN_UUID})+)\|", 
        raw_description
    )
    if id_from_desc:
        # get from raw description
        timing_uuid = id_from_desc[0]
    else:
        # set random timing_uuid
        timing_uuid = make_random_uuid(4)
        
    timing_description = re.findall(
        rf"([^\|]+)(?:\|(?:{PATTERN_UUID})+\|)?", 
        raw_description
    )[0].strip()
    return timing_description, timing_uuid

def get_timing_from_lines(
    lines: list[str], config_date: Optional[datetime] = None
) -> list[TimingConfig]:
    output, replaced = _get_timing_from_indexed_lines(
       dict(enumerate(lines)),
       config_date
    )
    return output, [line for _,line in sorted(replaced.items())]

def _get_timing_from_indexed_lines(
    lines: dict[int, str], config_date: Optional[datetime] = None
) -> list[TimingConfig]:
    output: list[TimingConfig] = []
    des, minutes, set_time, raw_timespec = None, None, None, None
    tim_des, tim_uuid, raw_description = None, None, None
    subtiming_lines: Optional[dict[int, str]] = None
    
    replaced_lines = copy.copy(lines)
    
    for lidx,line in sorted(lines.items()):
        if line.startswith(SPLITTER):
            # splitter
            break
        elif re.match(r"(?:\t+)?-.*", line):
            if subtiming_lines is None:
                subtiming_lines = {}
            subtiming_lines[lidx] = line[1:]
        else:
            # construct prev timing
            if des is not None and minutes is not None:
                if subtiming_lines:
                    subtimings, replaced_sublines = _get_timing_from_indexed_lines(subtiming_lines, config_date)
                    replaced_lines.update({k:indent_line(v) for k,v in replaced_sublines.items()})
                else:
                    subtimings = None
                output.append(TimingConfig(
                    tim_des,
                    minutes,
                    subtimings,
                    set_time,
                    uuid=tim_uuid,
                    raw_description=raw_description,
                    raw_timespec=raw_timespec
                ))
                
            # start accum next timing
            minutes = process_minutes(line)
            set_time = process_set_time(line, config_date)
            if not minutes:
                continue
            des = line.split("[")[0].strip()
            raw_timespec = line[line.find("["):].strip()
            tim_des, tim_uuid = split_desc_and_uuid(des)
            raw_description = f"{tim_des} |{tim_uuid}| "
            subtiming_lines = None
            replaced_lines[lidx] = raw_description+raw_timespec+"\n"
            
        
            
    # construct last timing
    if des is not None and minutes is not None:
        if subtiming_lines:
            subtimings, replaced_sublines = _get_timing_from_indexed_lines(subtiming_lines, config_date)
            replaced_lines.update({k:indent_line(v) for k,v in replaced_sublines.items()})
        else:
            subtimings = None
        tim_des, tim_uuid = split_desc_and_uuid(des)
        output.append(TimingConfig(
                    tim_des,
                    minutes,
                    subtimings,
                    set_time,
                    uuid=tim_uuid,
                    raw_description=raw_description,
                    raw_timespec=raw_timespec
                ))
    return output, replaced_lines
