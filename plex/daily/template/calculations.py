from datetime import datetime
import math
import os
from plex.daily.tasks import (
    DEFAULT_START_TIME,
)
from plex.daily.tasks.config import read_taskgroups
from plex.daily.tasks.logic import (
    get_taskgroups_from_timing_configs,
    sync_taskgroups_with_timing,
    calculate_times_in_taskgroup_list,
)
from plex.daily.timing import get_timing_from_file
from plex.daily.template.routines import update_routine_templates
from plex.daily.config_format import make_daily_filename, process_mins_to_timedelta


def evaluate_config_duration(
    filename: str, datestr: str, return_time_range: bool = False
) -> str:
    filename = make_daily_filename(filename, is_create_file=False)
    if not os.path.exists(filename):
        return "empty"
    date = datetime.strptime(datestr, "%Y-%m-%d").astimezone()
    date = date.replace(**DEFAULT_START_TIME)
    update_routine_templates(filename, datestr, is_main_file=False)
    timings = get_timing_from_file(filename, date)
    read_tasks = read_taskgroups(filename, date)
    if not read_tasks:
        taskgroups = get_taskgroups_from_timing_configs(timings)
        taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
    else:
        taskgroups = sync_taskgroups_with_timing(timings, read_tasks, date)
    if not taskgroups:
        return "empty"
    minutes = math.ceil((taskgroups[-1].end - taskgroups[0].start).total_seconds() / 60)
    duration = process_mins_to_timedelta(minutes)
    if not return_time_range:
        return f"{duration}"
    else:
        return f'{duration}|{taskgroups[-1].start.strftime("%-H:%M")}-{taskgroups[-1].end.strftime("%-H:%M")}'
