import dataclasses
import datetime
import os

from plex.daily.cache import load_from_cache, save_to_cache
from plex.daily.tasks import DEFAULT_START_TIME
from plex.daily.tasks.base import TaskGroup, convert_to_json
from plex.daily.tasks.config import read_taskgroups
from plex.daily.tasks.logic import calculate_times_in_taskgroup_list

DAILY_BASEDIR = "daily"

CACHE_FILE = "cache_files/endpoint/cache.pickle"


def match_uuids(taskgroups: list[TaskGroup], datestr: str) -> str:
    existing = load_from_cache(datestr, CACHE_FILE)
    taskToUUID = {}

    def changeUUID(taskgroups: list[TaskGroup]):
        for taskgroup in taskgroups:
            tasks = []
            for task in sorted(taskgroup.tasks, key=lambda task: task.start):
                uuid = task.uuid
                for idx, (euuid, prev) in enumerate(existing):
                    if task == prev:
                        uuid = euuid
                        existing.pop(idx)
                        break
                task = dataclasses.replace(
                    task, uuid=uuid, subtaskgroups=changeUUID(task.subtaskgroups)
                )
                taskToUUID[uuid] = task
                tasks.append(task)
            taskgroup.tasks = tasks
        return taskgroups

    taskgroups = changeUUID(taskgroups)
    save_to_cache(list(taskToUUID.items()), datestr, CACHE_FILE)
    return taskgroups


def get_json_str(datestr: str, filename: str):
    date = (
        datetime.datetime.strptime(datestr, "%Y-%m-%d")
        .astimezone()
        .replace(**DEFAULT_START_TIME)
    )
    taskgroups = read_taskgroups(filename, date)
    taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
    taskgroups = match_uuids(taskgroups, datestr)
    return convert_to_json(taskgroups)
