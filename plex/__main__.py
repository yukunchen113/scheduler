import os
import datetime
from pathlib import Path
from typing import Optional

from tap import tapify

from plex.daily import process_daily_file, sync_tasks_to_calendar

DAILY_BASEDIR = "daily"


def main(date: str, filename: Optional[str] = None, process_daily: bool = False, sync_calendar: bool = False) -> None:
    try:
        date = datetime.datetime.strptime(
            date, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid date '{date}' specified. must be in form 'YYYY-MM-DD'")
    if filename is None:
        filename = os.path.join(DAILY_BASEDIR, date+".txt")
    if process_daily:
        if not os.path.exists(filename):
            Path(filename).touch()
        process_daily_file(date, filename)

    if sync_calendar:
        if not os.path.exists(filename):
            raise ValueError(
                f"Daily file {filename} doesn't exist. Unable to sync to calendar.")
        sync_tasks_to_calendar(date, filename)


if __name__ == "__main__":
    tapify(main)
