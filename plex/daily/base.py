from datetime import datetime
import time
from plex.daily.tasks import (
    get_all_tasks_in_taskgroups,
    DEFAULT_START_TIME,
)
from plex.daily.tasks import TaskGroup
from plex.daily.tasks.config import read_taskgroups, write_taskgroups, process_taskgroups_from_lines, update_taskgroups_in_lines
from plex.daily.tasks.logic import (
    get_taskgroups_from_timing_configs,
    sync_taskgroups_with_timing,
    calculate_times_in_taskgroup_list,
)
from plex.daily.template import update_templates_in_file
from plex.daily.timing import get_timing_from_file
from plex.daily.timing.process import get_timing_from_lines
from plex.daily.calendar import (
    update_calendar_with_tasks,
    update_calendar_with_taskgroups,
)
from plex.daily.preprocess import apply_preprocessing
from plex.daily.timing.read import split_lines_across_splitter

CACHE_FILE = "cache_files/calendar_cache.pickle"

def split_splitter_and_tasks(task_lines_with_splitter: list[str]):
    if task_lines_with_splitter:
        splitter_line, task_lines = [task_lines_with_splitter[0]], task_lines_with_splitter[1:] # first line of tasks is the splitter
    else:
        splitter_line, task_lines = [], []
    return splitter_line, task_lines

def process_daily_file(datestr: str, filename: str) -> None:
    """Main entry point to processing the daily file

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """

    with open(filename) as file:
        lines = file.readlines()
    taskgroup_lines = process_daily_lines(datestr, lines)
    with open(filename, "w") as f:
        for line in taskgroup_lines:
            f.write(line)

def process_daily_lines(datestr: str, lines: list[str]) -> list[str]:
    """processes the lines for file

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """
    timing_lines, task_lines_with_splitter = split_lines_across_splitter(lines)
    splitter_line, task_lines = split_splitter_and_tasks(task_lines_with_splitter)

    date = datetime.strptime(datestr, "%Y-%m-%d").astimezone()
    date = date.replace(**DEFAULT_START_TIME)

    timing_lines, task_lines = apply_preprocessing(timing_lines, task_lines, datestr=datestr)

    # TODO: this can probably just take in timing lines
    new_lines = update_templates_in_file(timing_lines + splitter_line + task_lines, datestr=datestr, is_main_file=True)
    timing_lines, task_lines_with_splitter = split_lines_across_splitter(new_lines)
    splitter_line, task_lines = split_splitter_and_tasks(task_lines_with_splitter)

    timings, timing_lines = get_timing_from_lines(timing_lines, date)
    
    read_tasks = process_taskgroups_from_lines(
        task_lines,
        date
    )

    if not read_tasks:
        taskgroups = get_taskgroups_from_timing_configs(timings)
        taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
    else:
        taskgroups = sync_taskgroups_with_timing(timings, read_tasks, date)
    return update_taskgroups_in_lines(taskgroups, timing_lines + splitter_line + task_lines)


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
                write_taskgroups(taskgroups, filename)
            else:
                time.sleep(10)
