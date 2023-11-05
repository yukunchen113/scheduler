import os
from pathlib import Path
from typing import Optional

from tap import tapify

from plex.daily import process_daily_file

DAILY_BASEDIR = "daily"


def main(date: str, filename: Optional[str] = None, process_daily: bool = False) -> None:
    if process_daily:
        if filename is None:
            filename = os.path.join(DAILY_BASEDIR, date+".txt")
        if not os.path.exists(filename):
            Path(filename).touch()
        process_daily_file(date, filename)
    else:
        print("Not yet implemented")


if __name__ == "__main__":
    tapify(main)
