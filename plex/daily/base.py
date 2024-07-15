from datetime import datetime
import time
from plex.daily.tasks import (
    get_all_tasks_in_taskgroups,
    DEFAULT_START_TIME,
)
from plex.daily.tasks.config import read_taskgroups, write_taskgroups
from plex.daily.tasks.logic import (
    get_taskgroups_from_timing_configs,
    sync_taskgroups_with_timing,
    calculate_times_in_taskgroup_list,
)
from plex.daily.template import update_templates_in_file
from plex.daily.timing import get_timing_from_file
from plex.daily.calendar import (
    update_calendar_with_tasks,
    update_calendar_with_taskgroups,
)
from plex.daily.tasks.push_notes import sync_tasks_todo

CACHE_FILE = "cache_files/calendar_cache.pickle"


def process_daily_file(datestr: str, filename: str) -> None:
    """Main entry point to processing the daily file

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """
    date = datetime.strptime(datestr, "%Y-%m-%d").astimezone()
    date = date.replace(**DEFAULT_START_TIME)
    update_templates_in_file(filename, datestr=datestr, is_main_file=True)
    timings = get_timing_from_file(filename, date)
    read_tasks = read_taskgroups(filename, date)
    if not read_tasks:
        taskgroups = get_taskgroups_from_timing_configs(timings)
        taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
    else:
        taskgroups = sync_taskgroups_with_timing(timings, read_tasks, date)
    sync_tasks_todo(taskgroups)
    write_taskgroups(taskgroups, filename)


def sync_tasks_to_calendar(
    datestr: str, filename: str, push_only: bool = False
) -> None:
    """Syncs tasks to calendar.

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """
    date = datetime.strptime(datestr, "%Y-%m-%d").astimezone()
    date = date.replace(**DEFAULT_START_TIME)
    while True:
        taskgroups = read_taskgroups(filename, date)
        taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
        if push_only:
            tasks = get_all_tasks_in_taskgroups(taskgroups)
            update_calendar_with_tasks(tasks, datestr)
            break
        else:
            taskgroups = update_calendar_with_taskgroups(taskgroups, datestr)
            if taskgroups:
                # recalculate taskgroups
                taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
                sync_tasks_todo(taskgroups)
                write_taskgroups(taskgroups, filename)
            else:
                time.sleep(10)
