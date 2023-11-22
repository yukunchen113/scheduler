from datetime import datetime, timedelta
import math
import time
import os
import pickle
from plex.daily.tasks import get_all_tasks_in_taskgroups, DEFAULT_START_TIME, Task, TaskGroup
from plex.daily.tasks.base import update_taskgroups_with_changes
from plex.daily.tasks.config import read_taskgroups, write_taskgroups
from plex.daily.tasks.logic import (
    get_taskgroups_from_timing_configs,
    sync_taskgroups_with_timing,
)
from plex.daily.tasks.logic.calculations import calculate_times_in_taskgroup_list
from plex.daily.template import update_templates_in_file
from plex.daily.timing import get_timing_from_file
from plex.calendar import (
    get_all_plex_calendar_events,
    create_calendar_event,
    delete_calendar_event,
    get_event,
    update_calendar_event
)

CACHE_FILE = "cache_files/calendar_cache.pickle"


def process_daily_file(datestr: str, filename: str) -> None:
    """Main entry point to processing the daily file

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """
    date = datetime.strptime(datestr, "%Y-%m-%d").astimezone()
    date = date.replace(**DEFAULT_START_TIME)
    update_templates_in_file(filename, datestr=datestr)
    timings = get_timing_from_file(filename, date)
    read_tasks = read_taskgroups(filename, date)
    if not read_tasks:
        taskgroups = get_taskgroups_from_timing_configs(timings)
        taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
    else:
        taskgroups = sync_taskgroups_with_timing(timings, read_tasks, date)
    write_taskgroups(taskgroups, filename)


def update_calendar_with_tasks(tasks: list[Task], datestr: str) -> dict[str, Task]:
    """Syncs tasks with calendar tasks.

    Given a cache (task_mapping), will update, create, or delete depending on __eq__ evaluation of tasks

    Will update if __eq__ is true but other fields are not the same.
    Will create if task doesn't exist in calendar
    Will delete if task doesn't exist in cache or in tasks

    Args:
        tasks (list[Task]): list of tasks to be created
        datestr (str): datestr. To be used as key for calendar
        task_mapping (dict[str, Task]): cache

    Returns:
        dict[str, Task]: new updated cache (task_mapping)
    """
    task_mapping: dict[str, Task] = load_from_cache(datestr)
    date_id = datestr.replace("-", "")
    date = datetime.strptime(datestr, "%Y-%m-%d").astimezone()
    date = date.replace(**DEFAULT_START_TIME)
    cal_event_ids = [i.event_id for i in get_all_plex_calendar_events(
        date-timedelta(days=10), date_id=date_id)]

    # delete tasks that don't exist in task_mapping
    # filter out tasks that have changed
    new_task_mapping = {}
    for event_id, task in task_mapping.items():
        if task in tasks and event_id in cal_event_ids:
            cal_event_ids.pop(cal_event_ids.index(event_id))
            new_task = tasks.pop(tasks.index(task))
            # use task from new tasks to be created
            new_task_mapping[event_id] = new_task
            if task.start != new_task.start or task.end != new_task.end:
                assert new_task.start and new_task.end
                update_calendar_event(event_id, summary=task.name, start=new_task.start,
                                      end=new_task.end, notes=task.notes, date_id=date_id)
    task_mapping = new_task_mapping
    if len(cal_event_ids):
        print(
            f"Deleting {len(cal_event_ids)} tasks that are in the calendar but not in latest config"
        )
    for event_id in cal_event_ids:
        # delete events that are in the cal but not in task_mapping
        # we do this since we don't have a way to convert from event to task
        # so even if an event matches a task, since it's not in the cache, delete.
        delete_calendar_event(get_event(event_id))

    # create tasks that don't exist in task_mapping
    if len(tasks):
        print(f"Creating {len(tasks)} tasks.")
    for task in tasks:
        assert task.start and task.end
        try:
            event_id = create_calendar_event(summary=task.name, start=task.start,
                                             end=task.end, notes=task.notes, date_id=date_id)
        except Exception as exc:
            print(
                f"Unable to add task '{task}'. Exception: {str(exc)}")
        task_mapping[event_id] = task

    save_to_cache(task_mapping, datestr)
    return task_mapping


def get_updates_from_calendar(task_mapping: dict[str, Task]) -> dict[str, dict[str, int]]:
    # get new diffs
    changes = {}
    for event_id, task in task_mapping.items():
        assert task.start and task.end
        event = get_event(event_id)
        start_diff = math.ceil((event.start - (task.start -
                                               timedelta(minutes=task.start_diff or 0))).total_seconds()/60)
        end_diff = math.ceil((event.end - (task.end -
                                           timedelta(minutes=task.end_diff or 0))).total_seconds()/60)
        if not start_diff and task.start_diff is None:
            start_diff = None
        if not end_diff and task.end_diff is None:
            end_diff = None
        if start_diff != task.start_diff or end_diff != task.end_diff:
            changes[task.uuid] = {
                "start_diff": start_diff,
                "end_diff": end_diff
            }
    return changes


def load_from_cache(datestr: str):
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "rb") as file:
        return pickle.load(file)


def save_to_cache(data: object, datestr: str):
    if not os.path.exists(CACHE_FILE):
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "wb") as file:
        pickle.dump(data, file)


def update_calendar_with_taskgroups(taskgroups: list[TaskGroup], datestr: str) -> list[TaskGroup]:
    # modify existing calendar
    tasks = get_all_tasks_in_taskgroups(taskgroups)
    task_mapping = update_calendar_with_tasks(tasks, datestr)
    changes = get_updates_from_calendar(task_mapping)
    if changes:
        print(f"Found Changed Items: {changes}")
        return update_taskgroups_with_changes(taskgroups, changes)
    return []


def sync_tasks_to_calendar(datestr: str, filename: str, push_only: bool = False) -> None:
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
            taskgroups = update_calendar_with_taskgroups(
                taskgroups, datestr)
            if taskgroups:
                # recalculate taskgroups
                taskgroups = calculate_times_in_taskgroup_list(
                    taskgroups, date)
                write_taskgroups(taskgroups, filename)
            else:
                time.sleep(10)
