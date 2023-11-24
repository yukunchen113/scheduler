import re
from typing import Optional
from datetime import datetime
import os
from pathlib import Path

DAILY_BASEDIR = "daily"

SPLITTER = "-------------"

TIMEDELTA_FORMAT = r"\d+(?:hr|h)?(?:\d+)?"
TIME_FORMAT = r"\d\d?(?::\d\d)?(?:am|pm|PM|AM)?"


def process_time_to_datetime(timestr: str, default_datetime: Optional[datetime] = None):
    if re.fullmatch(TIME_FORMAT, timestr) is None:
        raise ValueError(f"Invalid format: '{timestr}'")
    timestr = timestr.lower()
    if "am" in timestr or "pm" in timestr:
        if ":" in timestr:
            time = datetime.strptime(timestr, "%I:%M%p").astimezone()
        else:
            time = datetime.strptime(timestr, "%I%p").astimezone()
    else:
        time = datetime.strptime(timestr, "%H:%M").astimezone()
    if default_datetime is None:
        output = datetime.now().astimezone()
    else:
        output = default_datetime
    return output.replace(microsecond=0, second=0, minute=time.minute, hour=time.hour)


def process_timedelta_to_mins(timedelta_str: str) -> int:
    if re.fullmatch(TIMEDELTA_FORMAT, timedelta_str) is None:
        raise ValueError(f"Invalid format supplied: '{timedelta_str}'")
    w, x, y = re.findall(r"(\d+)(h)?r?(\d+)?", timedelta_str)[0]
    if w == "":
        raise ValueError(f"Time must be specified for {timedelta_str}")
    y = y or 0
    return int(w) * (60 if x == "h" else 1) + int(y)


def process_mins_to_timedelta(minutes: int) -> str:
    hours, minutes = divmod(minutes, 60)
    output = ""
    if hours:
        output += f"{hours}h"
    if minutes:
        output += f"{minutes}"
    if not hours and not minutes:
        output = "0"
    return output


def add_splitter(filename: str) -> None:
    with open(filename) as f:
        for line in f.readlines():
            if line.startswith(SPLITTER):
                return
    with open(filename, "a") as f:
        f.write(f"\n{SPLITTER}\n")


def make_daily_filename(filename: str, is_create_file: bool = False) -> str:
    assert (
        not "." in filename
    ), "Specify filename without extension. Filename must not contain '.'"
    filename = os.path.join(DAILY_BASEDIR, filename)
    # backwards compatibility for .txt file:
    if os.path.exists(filename + ".txt"):
        os.rename(filename + ".txt", filename + ".ans")
    filename = filename + ".ans"
    if is_create_file:
        if not os.path.exists(filename):
            Path(filename).touch()
    return filename
