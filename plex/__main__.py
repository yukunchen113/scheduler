import datetime
import os
import threading
import time
from pathlib import Path
from typing import Optional

from tap import tapify

from plex.daily import process_daily_file, sync_tasks_to_calendar
from plex.daily.base import TaskSource
from plex.daily.config_format import make_daily_filename
from plex.daily.endpoint import get_json_str
from plex.daily.tasks.push_notes import notion_requestor, overwrite_tasks_in_notion
from plex.notion_api.page import clear_page_cache

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
    is_skip_calendar: bool = False,
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
        is_skip_calendar (bool, optional): skip calendar updates
    """
    source = TaskSource(source)
    threading.Thread(target=notion_requestor, daemon=True).start()

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
        if not is_skip_calendar:
            print("Pushing to calendar")
            sync_tasks_to_calendar(datestr, filename, push_only=True)

    if autoupdate:
        print(f"Starting Auto Update mode. Source: {source}")
        update_process_time = time.time()
        update_calendar_time = time.time()
        calendar_retry_times = 3

        update_window = []
        is_sleep_mode = False
        process_retry_times = 5
        overwrite_retry_times = 3
        while True:
            if time.time() >= update_process_time:
                try:
                    is_changed = process_daily_file(datestr, filename, source)
                    process_retry_times = 5
                except Exception as err:
                    print(
                        f"Process ERROR (retries left - {process_retry_times}): {err}"
                    )
                    if process_retry_times <= 0:
                        print(
                            "Process ERROR Attempting Overwrite "
                            f"(retries left - {overwrite_retry_times}): {err}"
                        )
                        try:
                            overwrite_tasks_in_notion(datestr)
                            overwrite_retry_times = 3
                            process_retry_times = 5
                        except Exception as err:
                            if overwrite_retry_times <= 0:
                                print(f"Process ERROR Error...")
                                raise err
                            else:
                                overwrite_retry_times -= 1
                    else:
                        process_retry_times -= 1
                    clear_page_cache()
                    time.sleep(3)
                    continue

                update_window.append(is_changed)
                while len(update_window) > 5:
                    update_window.pop(0)
                if any(update_window):
                    update_process_time = time.time() + 1  # if updated lines
                    if is_sleep_mode:
                        print("Changing to fast update mode. Changes detected")
                    is_sleep_mode = False
                else:
                    update_process_time = time.time() + 5  # sleep mode
                    if not is_sleep_mode:
                        print("Changing to sleep mode after no changes detected")
                    is_sleep_mode = True

            if not is_skip_calendar and time.time() >= update_calendar_time:
                try:
                    sync_tasks_to_calendar(datestr, filename, push_only=True)
                    calendar_retry_times = 3
                except Exception as err:
                    print(
                        f"Calendar ERROR: (retries left - {calendar_retry_times}): {err}"
                    )
                    if calendar_retry_times <= 0:
                        print(f"Calendar ERROR Exiting...")
                        raise err
                    calendar_retry_times -= 1

                update_calendar_time = time.time() + 60


if __name__ == "__main__":
    tapify(main)
