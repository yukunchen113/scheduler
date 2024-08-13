import datetime
import os
import time
from pathlib import Path
from typing import Optional

from tap import tapify

from plex.daily import process_daily_file, sync_tasks_to_calendar
from plex.daily.base import TaskSource
from plex.daily.config_format import make_daily_filename
from plex.daily.endpoint import get_json_str
from plex.daily.tasks.push_notes import overwrite_tasks_in_notion, sync_tasks_to_notion

DAILY_BASEDIR = "daily"


def main(
    tomorrow: bool = False,
    date: Optional[str] = None,
    filename: Optional[str] = None,
    no_process_daily: bool = False,
    push: bool = False,
    sync: bool = False,
    print_json: bool = False,
    autoupdate: bool = False,
    source: str = "file",
) -> None:
    """Plex: Planning and execution command line tool

    Args:
        tomorrow (bool, optional): if process tomorrow's file. Defaults to False.
        date (Optional[str], optional): process specified date. Defaults to None.
        filename (Optional[str], optional): process specifed filename, will still need to provide specified date for calendar sync. Defaults to None.
        no_process_daily (bool, optional): don't process the daily file. Defaults to False.
        push (bool, optional): one time push to google calendar. Defaults to False.
        sync (bool, optional): start up sync server to sync calendar and file, while processing tasks. Defaults to False.
        print_json (bool, optional): prints json tasklists, doesn't include information from syncing with calendar
        auto_update (bool, optional): sets into autoupdate mode, will constantly look to update and for triggers
        source (bool, optional): source of where to get the task schedule. Defaults to "file".
            If this is the first time running with something other than file, remember to first push your changes.
            Available options: (file, notion)
    """
    source = TaskSource(source)

    if date:
        assert not tomorrow, "cannot specify tomorrow when date is specified."
        try:
            # validate datestr
            datestr = datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid datestr '{datestr}' specified. must be in form 'YYYY-MM-DD'"
            )
    elif tomorrow:
        datestr = (datetime.datetime.today() + datetime.timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
    else:
        datestr = datetime.datetime.today().strftime("%Y-%m-%d")

    if filename is None:
        filename = datestr
    filename = make_daily_filename(filename, not no_process_daily)
    if not no_process_daily:
        process_daily_file(datestr, filename, source)

    if print_json:
        print(get_json_str(datestr, filename))

    if sync:
        assert not push
        if not os.path.exists(filename):
            raise ValueError(
                f"Daily file {filename} doesn't exist. Unable to sync to calendar."
            )
        sync_tasks_to_calendar(datestr, filename, push_only=False)

    elif push:
        if not os.path.exists(filename):
            raise ValueError(f"Daily file {filename} doesn't exist. Unable to push.")
            # write out contents
        print("Pushing Tasks To Notion")
        overwrite_tasks_in_notion(datestr)
        print("Pushing to calendar")
        sync_tasks_to_calendar(datestr, filename, push_only=True)

    if autoupdate:
        print(f"Starting Auto Update mode. Source: {source}")
        update_process_time = time.time()
        update_calendar_time = time.time()
        while True:
            if time.time() >= update_process_time:
                process_daily_file(datestr, filename, source)
                update_process_time = time.time() + 3

            if time.time() >= update_calendar_time:
                sync_tasks_to_calendar(datestr, filename, push_only=True)
                update_calendar_time = time.time() + 60
            time.sleep(1)


if __name__ == "__main__":
    tapify(main)
