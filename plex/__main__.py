import os
import datetime
from pathlib import Path
from typing import Optional

from tap import tapify

from plex.daily import process_daily_file, sync_tasks_to_calendar
from plex.daily.config_format import make_daily_filename

DAILY_BASEDIR = "daily"


def main(
    date: str,
    filename: Optional[str] = None,
    process_daily: bool = False,
    push_to_calendar: bool = False,
    sync_calendar: bool = False,
) -> None:
    try:
        date = datetime.datetime.strptime(date, "%Y-%m-%d")
        datestr = date.strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid datestr '{datestr}' specified. must be in form 'YYYY-MM-DD'"
        )

    if filename is None:
        filename = datestr
    filename = make_daily_filename(filename, process_daily)
    if process_daily:
        process_daily_file(datestr, filename)

    if sync_calendar:
        assert not push_to_calendar
        if not os.path.exists(filename):
            raise ValueError(
                f"Daily file {filename} doesn't exist. Unable to sync to calendar."
            )
        sync_tasks_to_calendar(datestr, filename, push_only=False)

    elif push_to_calendar:
        if not os.path.exists(filename):
            raise ValueError(
                f"Daily file {filename} doesn't exist. Unable to push to calendar."
            )
        sync_tasks_to_calendar(datestr, filename, push_only=True)


if __name__ == "__main__":
    tapify(main)
