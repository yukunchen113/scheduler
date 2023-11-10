from datetime import datetime, timedelta
from plex.daily.tasks import get_all_tasks_in_taskgroups, DEFAULT_START_TIME
from plex.daily.tasks.config import read_taskgroups, write_taskgroups
from plex.daily.tasks.logic import (
    calculate_times_in_taskgroup,
    get_taskgroup_from_timing_configs,
    sync_taskgroups_with_timing,
)
from plex.daily.tasks.logic.calculations import calculate_times_in_taskgroup_list
from plex.daily.template import update_templates_in_file
from plex.daily.timing import get_timing_from_file
from plex.calendar import get_all_plex_calendar_events, create_calendar_event, delete_calendar_event


def process_daily_file(datestr: str, filename: str) -> None:
    """Main entry point to processing the daily file

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """
    date = datetime.strptime(datestr, "%Y-%m-%d")
    date = date.replace(**DEFAULT_START_TIME)
    update_templates_in_file(filename, datestr=datestr)
    timings = get_timing_from_file(filename)
    read_tasks = read_taskgroups(filename, date)
    if not read_tasks:
        taskgroup = get_taskgroup_from_timing_configs(timings)
        taskgroup = calculate_times_in_taskgroup(taskgroup, date)
        tasks_to_write = [taskgroup]
    else:
        tasks_to_write = sync_taskgroups_with_timing(timings, read_tasks, date)
    write_taskgroups(tasks_to_write, filename)


def sync_tasks_to_calendar(datestr: str, filename: str) -> None:
    """Syncs tasks to calendar.

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """
    date = datetime.strptime(datestr, "%Y-%m-%d")
    date = date.replace(**DEFAULT_START_TIME)
    taskgroups = read_taskgroups(filename, date)
    taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
    tasks = get_all_tasks_in_taskgroups(taskgroups)
    date_id = datestr.replace("-", "")
    for event in get_all_plex_calendar_events(date-timedelta(days=10), date_id=date_id):
        delete_calendar_event(event)
    for task in tasks:
        try:
            create_calendar_event(summary=task.name, start=task.start,
                                  end=task.end, notes=task.notes, date_id=date_id)
        except Exception as exc:
            print(f"Unable to add task '{task}'. Exception: {str(exc)}")
