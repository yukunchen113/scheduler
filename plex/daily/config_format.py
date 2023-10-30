import re
from datetime import datetime

SPLITTER = "-------------"

TIMEDELTA_FORMAT = r"\d+(?:hr|h)?(?:\d+)?"
TIME_FORMAT = r"\d\d?(?::\d\d)?(?:am|pm|PM|AM)?"


def process_time_to_datetime_now(timestr: str):
    if re.fullmatch(TIME_FORMAT, timestr) is None:
        raise ValueError(f"Invalid format: '{timestr}'")
    ptimestr = timestr.lower()
    extra_hr = None
    if ptimestr.endswith("am"):
        extra_hr = 0
        ptimestr = ptimestr.replace("am", "")
    elif ptimestr.endswith("pm"):
        extra_hr = 12
        ptimestr = ptimestr.replace("pm", "")

    output = datetime.now()
    timelist = ptimestr.split(":")
    hour = int(timelist[0])
    if not extra_hr is None:
        if hour > 12:
            raise ValueError(f"Invalid time: '{timestr}'")
        hour += extra_hr
    if len(timelist) > 1:
        minute = int(timelist[1])
    else:
        minute = 0
    return output.replace(microsecond=0, second=0, minute=minute, hour=hour)


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
