import os
from typing import Optional
from plex.daily.tasks.config import read_taskgroups, write_taskgroups
from plex.daily.tasks.logic import (
    calculate_times_in_taskgroup,
    get_taskgroup_from_timing_configs,
    sync_taskgroups_with_timing,
)
from plex.daily.template import update_templates_in_file
from plex.daily.timing import get_timing_from_file


def process_daily_file(datestr: str, filename: str) -> None:
    """Main entry point to processing the daily file

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """
    update_templates_in_file(filename, datestr=datestr)
    timings = get_timing_from_file(filename)
    read_tasks = read_taskgroups(filename)
    if not read_tasks:
        taskgroup = get_taskgroup_from_timing_configs(timings)
        taskgroup = calculate_times_in_taskgroup(taskgroup)
        tasks_to_write = [taskgroup]
    else:
        tasks_to_write = sync_taskgroups_with_timing(timings, read_tasks)
    write_taskgroups(tasks_to_write, filename)
