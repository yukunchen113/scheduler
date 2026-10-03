import datetime
import os
import tempfile

import pytest

from plex.weekly import (
    DAY_HEADER_PATTERN,
    STATUS_LINE_PATTERN,
    format_duration,
    get_week_dates,
    simulate_day_lines,
)


def test_get_week_dates():
    # 2026-10-07 is a Wednesday
    ref_date = datetime.date(2026, 10, 7)
    dates = get_week_dates(ref_date)
    assert len(dates) == 7
    assert dates[0] == datetime.date(2026, 10, 5)  # Monday
    assert dates[-1] == datetime.date(2026, 10, 11)  # Sunday


def test_format_duration():
    assert format_duration(45) == "45m"
    assert format_duration(60) == "1h00m"
    assert format_duration(125) == "2h05m"


def test_day_header_pattern():
    line1 = "=== Monday (2026-10-05) ========================================================"
    match1 = DAY_HEADER_PATTERN.match(line1)
    assert match1 is not None
    assert match1.group(1) == "Monday"
    assert match1.group(2) == "2026-10-05"

    line2 = "=== Sunday (2026-10-11) ==="
    match2 = DAY_HEADER_PATTERN.match(line2)
    assert match2 is not None
    assert match2.group(1) == "Sunday"
    assert match2.group(2) == "2026-10-11"


def test_status_line_pattern():
    status1 = "# [07:30 - 20:45 | 9h05m scheduled | 4h10m slack | Status: OK]"
    assert STATUS_LINE_PATTERN.match(status1) is not None

    not_status = "# just a comment"
    assert STATUS_LINE_PATTERN.match(not_status) is None


def test_simulate_day_lines():
    lines = [
        "wake up [20]\n",
        "get ready [30]\n",
        "lecture [1h30] (10am)\n",
        "study [2h]\n",
    ]
    result = simulate_day_lines(lines, "2026-10-05")
    assert result["total_mins"] == 20 + 30 + 90 + 120
    assert result["status"] == "OK"
    assert result["start_time"] is not None
    assert result["end_time"] is not None


def test_extract_section_lines_from_file(tmp_path):
    routine_file = tmp_path / "custom_routine.txt"
    routine_file.write_text(
        "mon:\n"
        "lecture [1h30] (10am)\n"
        "lab [2h] (14:00)\n\n"
        "tue:\n"
        "seminar [1h] (11:00)\n\n"
        "weekdays:\n"
        "standup [15] (9:30am)\n"
    )
    from plex.weekly import extract_section_lines_from_file

    mon_lines = extract_section_lines_from_file(str(routine_file), "mon")
    assert len(mon_lines) == 2
    assert "lecture [1h30] (10am)\n" in mon_lines
    assert "lab [2h] (14:00)\n" in mon_lines

    tue_lines = extract_section_lines_from_file(str(routine_file), "tue")
    assert len(tue_lines) == 1
    assert "seminar [1h] (11:00)\n" in tue_lines

    # Wed falls back to weekdays
    wed_lines = extract_section_lines_from_file(str(routine_file), "wed")
    assert len(wed_lines) == 1
    assert "standup [15] (9:30am)\n" in wed_lines


def test_init_weekly_file_with_routine_template(tmp_path):
    from plex.weekly import init_weekly_file

    out_file = tmp_path / "2026-W41.txt"
    ref_date = datetime.date(2026, 10, 5)

    # Initialize with school template
    init_weekly_file(
        target_date=ref_date,
        overwrite=True,
        templates=["school"],
        filename=str(out_file),
        expand=True,
    )
    assert out_file.exists()
    content = out_file.read_text()

    # Prepopulated Monday classes should be expanded in the file
    assert "=== Monday (2026-10-05)" in content
    assert "lecture [1h30] (10am)" in content
    assert "lab [2h] (14:00)" in content
    # Status line should be evaluated in-place
    assert "scheduled" in content


def test_init_weekly_file_with_python_generator(tmp_path):
    from plex.weekly import init_weekly_file

    gen_script = tmp_path / "mock_gen.py"
    gen_script.write_text(
        "import argparse\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--datestr', type=str)\n"
        "parser.add_argument('--weekday', type=str, default=None)\n"
        "args = parser.parse_args()\n"
        "if args.weekday in ['mon', 'wed']:\n"
        "    print('team sync [45] (11am)')\n"
    )

    out_file = tmp_path / "2026-W42.txt"
    ref_date = datetime.date(2026, 10, 5)

    init_weekly_file(
        target_date=ref_date,
        overwrite=True,
        templates=[str(gen_script)],
        filename=str(out_file),
    )
    assert out_file.exists()
    content = out_file.read_text()
    assert "team sync [45] (11am)" in content


def test_init_weekly_file_macro_mode(tmp_path):
    from plex.weekly import init_weekly_file

    out_file = tmp_path / "2026-W43.txt"
    ref_date = datetime.date(2026, 10, 5)

    init_weekly_file(
        target_date=ref_date,
        overwrite=True,
        templates=["school"],
        filename=str(out_file),
        expand=False,
    )
    content = out_file.read_text()
    assert "{school:mon}" in content
