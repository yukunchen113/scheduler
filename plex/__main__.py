import os
import datetime
from pathlib import Path
from typing import Optional

from tap import tapify

from plex.daily import process_daily_file, sync_tasks_to_calendar
from plex.daily.config_format import make_daily_filename

DAILY_BASEDIR = "daily"


def main(
    tomorrow: bool = False,
    date: Optional[str] = None,
    filename: Optional[str] = None,
    no_process_daily: bool = False,
    push: bool = False,
    sync: bool = False,
) -> None:
    """Plex: Planning and execution command line tool

    Args:
        tomorrow (bool, optional): if process tomorrow's file. Defaults to False.
        date (Optional[str], optional): process specified date. Defaults to None.
        filename (Optional[str], optional): process specifed filename, will still need to provide specified date for calendar sync. Defaults to None.
        no_process_daily (bool, optional): don't process the daily file. Defaults to False.
        push (bool, optional): one time push to google calendar. Defaults to False.
        sync (bool, optional): start up sync server to sync calendar and file, while processing tasks. Defaults to False.
    """
    if date:
        assert not tomorrow, 'cannot specify tomorrow when date is specified.'
        try:
            # validate datestr
            datestr = datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid datestr '{datestr}' specified. must be in form 'YYYY-MM-DD'"
            )
    elif tomorrow:
        datestr = (datetime.datetime.today()+datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        datestr = datetime.datetime.today().strftime("%Y-%m-%d")

    if filename is None:
        filename = datestr
    filename = make_daily_filename(filename, not no_process_daily)
    if not no_process_daily:
        process_daily_file(datestr, filename)

    if sync:
        assert not push
        if not os.path.exists(filename):
            raise ValueError(
                f"Daily file {filename} doesn't exist. Unable to sync to calendar."
            )
        sync_tasks_to_calendar(datestr, filename, push_only=False)

    elif push:
        if not os.path.exists(filename):
            raise ValueError(
                f"Daily file {filename} doesn't exist. Unable to push to calendar."
            )
        sync_tasks_to_calendar(datestr, filename, push_only=True)


if __name__ == "__main__":
    tapify(main)
