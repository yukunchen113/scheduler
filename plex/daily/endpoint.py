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


def get_json_str(datestr: str, filename: str):
    date = (
        datetime.datetime.strptime(datestr, "%Y-%m-%d")
        .astimezone()
        .replace(**DEFAULT_START_TIME)
    )
    taskgroups = read_taskgroups(filename, date)
    taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
    return convert_to_json(taskgroups)
