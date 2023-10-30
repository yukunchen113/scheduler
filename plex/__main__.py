from tap import tapify

from plex.daily import process_daily_file


def main(filename: str, process_daily: bool = False) -> None:
    if process_daily:
        process_daily_file(filename)
    else:
        print("Not yet implemented")


if __name__ == "__main__":
    tapify(main)
