"""
Plex Weekly Planning & Simulation Utility for VS Code

A unified, single-file weekly planner:
- All 7 days in one buffer for fast VS Code keyboard manipulation (Alt+Up/Down)
- School schedules and routines pre-populated via routine template generators (.txt or .py)
- Live in-place calculation of scheduled hours, slack, and bedtime warnings
- Export to daily/*.ans files for seamless execution
"""

import argparse
import datetime
import math
import os
import re
import subprocess
import sys
import time
from typing import Optional

from plex.daily.config_format import (
    SPLITTER,
    make_daily_filename,
    process_mins_to_timedelta,
)
from plex.daily.tasks import DEFAULT_START_TIME, Task
from plex.daily.tasks.logic import (
    calculate_times_in_taskgroup_list,
    get_taskgroups_from_timing_configs,
)
from plex.daily.template.routines import read_sections_from_template
from plex.daily.template.update import update_templates
from plex.daily.timing.process import get_timing_from_lines
from plex.transform.base import TRANSFORM, LineSection, Metadata

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_FULL = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
WEEKLY_DIR = "weekly"
SCHOOL_ROUTINE = "routines/school.txt"
DEFAULT_BED_TIME = "23:30"

DAY_HEADER_PATTERN = re.compile(r"^===+\s*([A-Za-z]+)\s*(?:\(([\d-]+)\))?\s*===+")
STATUS_LINE_PATTERN = re.compile(r"^#\s*\[.*\]\s*$")


def get_week_dates(reference_date: datetime.date) -> list[datetime.date]:
    """Returns the Monday-Sunday dates for the week containing reference_date."""
    monday = reference_date - datetime.timedelta(days=reference_date.weekday())
    return [monday + datetime.timedelta(days=i) for i in range(7)]


def get_weekly_filename(reference_date: datetime.date) -> str:
    """Returns weekly/YYYY-WWW.txt (e.g. weekly/2026-W41.txt)."""
    year, week, _ = reference_date.isocalendar()
    os.makedirs(WEEKLY_DIR, exist_ok=True)
    return os.path.join(WEEKLY_DIR, f"{year}-W{week:02d}.txt")


def format_duration(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def resolve_routine_path(name_or_path: str) -> str:
    """Resolves a routine name or path to an existing file."""
    if os.path.exists(name_or_path):
        return name_or_path
    as_routine = os.path.join("routines", name_or_path)
    if os.path.exists(as_routine):
        return as_routine
    if not name_or_path.endswith((".txt", ".py", ".yaml", ".json")):
        as_txt = os.path.join("routines", f"{name_or_path}.txt")
        if os.path.exists(as_txt):
            return as_txt
        as_py = os.path.join("routines", f"{name_or_path}.py")
        if os.path.exists(as_py):
            return as_py
    return name_or_path


def extract_section_lines_from_file(filename: str, section_name: str) -> list[str]:
    """Extracts raw task lines under a specific section heading (e.g. 'mon:') from a routine template file."""
    if not os.path.exists(filename):
        return []
    with open(filename, "r") as f:
        content = f.readlines()

    section_header = re.compile(r"^([A-Za-z0-9_-]+):\s*$")
    current_section = None
    sections: dict[str, list[str]] = {}

    for line in content:
        match = section_header.match(line.strip())
        if match:
            current_section = match.group(1).lower()
            sections[current_section] = []
        elif current_section is not None:
            if line.strip():
                sections[current_section].append(
                    line if line.endswith("\n") else line + "\n"
                )
        else:
            if line.strip():
                sections.setdefault("__default__", []).append(
                    line if line.endswith("\n") else line + "\n"
                )

    sec_key = section_name.lower()
    if sec_key in sections and sections[sec_key]:
        return sections[sec_key]
    if (
        sec_key in ["mon", "tue", "wed", "thu", "fri"]
        and "weekdays" in sections
        and sections["weekdays"]
    ):
        return sections["weekdays"]
    if sec_key in ["sat", "sun"] and "weekends" in sections and sections["weekends"]:
        return sections["weekends"]
    if "__default__" in sections and len(sections) == 1 and sections["__default__"]:
        return sections["__default__"]
    return []


def generate_day_lines_from_source(
    source: str,
    datestr: str,
    weekday_short: str,
    expand: bool = True,
) -> list[str]:
    """Generates task lines for a specific day from a routine template (.txt) or generator script (.py)."""
    resolved = resolve_routine_path(source)
    if not os.path.exists(resolved):
        print(
            f"Warning: Routine template/generator '{source}' not found at '{resolved}'."
        )
        return []

    if resolved.endswith(".py"):
        # Executable Python routine generator
        cmd = [
            sys.executable,
            resolved,
            "--datestr",
            datestr,
            "--weekday",
            weekday_short,
        ]
        try:
            output = subprocess.run(cmd, env=os.environ, capture_output=True, text=True)
            if (
                output.returncode != 0
                and "unrecognized argument" in output.stderr.lower()
            ):
                # Fallback to --datestr only
                cmd = [sys.executable, resolved, "--datestr", datestr]
                output = subprocess.run(
                    cmd, env=os.environ, capture_output=True, text=True
                )
            if output.returncode == 0 and output.stdout:
                return [
                    line + "\n" for line in output.stdout.splitlines() if line.strip()
                ]
            elif output.returncode != 0 and output.stderr:
                print(f"Warning: Generator '{source}' failed: {output.stderr.strip()}")
        except Exception as err:
            print(f"Error running generator script '{source}': {err}")
        return []

    # Text template file (e.g. routines/school.txt)
    base_name = os.path.splitext(os.path.basename(resolved))[0]

    if expand:
        raw_lines = extract_section_lines_from_file(resolved, weekday_short)
        if raw_lines:
            return raw_lines
        return []

    # Macro reference mode
    sections = read_sections_from_template(resolved, datestr, is_main_file=False)
    available_sections = [s.strip(":\n ").lower() for s in sections.keys()]

    if weekday_short in available_sections:
        return [f"{{{base_name}:{weekday_short}}}\n"]
    elif (
        weekday_short in ["mon", "tue", "wed", "thu", "fri"]
        and "weekdays" in available_sections
    ):
        return [f"{{{base_name}:weekdays}}\n"]
    elif weekday_short in ["sat", "sun"] and "weekends" in available_sections:
        return [f"{{{base_name}:weekends}}\n"]
    elif "__default__" in available_sections and len(available_sections) == 1:
        return [f"{{{base_name}}}\n"]

    return []


def simulate_day_lines(lines: list[str], datestr: str) -> dict:
    """Simulates a day's schedule from lines using Plex's engine."""
    date_dt = (
        datetime.datetime.strptime(datestr, "%Y-%m-%d")
        .astimezone()
        .replace(**DEFAULT_START_TIME)
    )

    filtered_lines = [
        line
        for line in lines
        if line.strip()
        and not line.startswith("#")
        and not line.startswith("=")
        and not line.startswith(SPLITTER)
    ]
    if not filtered_lines:
        return {
            "tasks": [],
            "total_mins": 0,
            "span_mins": 0,
            "slack_mins": 0,
            "start_time": None,
            "end_time": None,
            "status": "EMPTY",
            "summary_str": "No tasks planned",
        }

    TRANSFORM.clear()
    TRANSFORM.start_recording()
    timing_lines = [
        TRANSFORM.append(line, Metadata(section=LineSection.timing))
        for line in filtered_lines
    ]
    timing_lines = update_templates(timing_lines, datestr=datestr, is_main_file=True)
    timings, _ = get_timing_from_lines(timing_lines, date_dt)
    taskgroups = get_taskgroups_from_timing_configs(timings)
    taskgroups = calculate_times_in_taskgroup_list(taskgroups, date_dt)
    TRANSFORM.stop_recording()

    tasks: list[Task] = []
    for tg in taskgroups:
        tasks.extend(tg.tasks)

    total_mins = sum(t.time for t in tasks)
    start_time = tasks[0].start if tasks else None
    end_time = tasks[-1].end if tasks else None

    # Check overlaps
    overlaps = []
    for i in range(len(tasks) - 1):
        if tasks[i].end and tasks[i + 1].start and tasks[i].end > tasks[i + 1].start:
            overlaps.append(tasks[i].name)

    span_mins = 0
    slack_mins = 0
    if start_time and end_time:
        span_mins = math.ceil((end_time - start_time).total_seconds() / 60)
        slack_mins = max(0, span_mins - total_mins)

    status = "OK"
    if overlaps:
        status = f"OVERLAP ({len(overlaps)})"
    elif end_time and end_time.strftime("%H:%M") > DEFAULT_BED_TIME:
        diff_bed = math.ceil(
            (end_time - end_time.replace(hour=23, minute=30)).total_seconds() / 60
        )
        status = f"PAST BEDTIME (+{diff_bed}m)"
    elif span_mins > 15 * 60:
        status = "TIGHT (>15h span)"

    start_str = start_time.strftime("%H:%M") if start_time else "--:--"
    end_str = end_time.strftime("%H:%M") if end_time else "--:--"
    summary = f"{start_str} - {end_str} | {format_duration(total_mins)} scheduled | {format_duration(slack_mins)} slack | Status: {status}"

    return {
        "tasks": tasks,
        "total_mins": total_mins,
        "span_mins": span_mins,
        "slack_mins": slack_mins,
        "start_time": start_time,
        "end_time": end_time,
        "status": status,
        "summary_str": summary,
    }


def init_weekly_file(
    target_date: Optional[datetime.date] = None,
    overwrite: bool = False,
    templates: Optional[list[str]] = None,
    no_daily: bool = False,
    filename: Optional[str] = None,
    expand: bool = True,
) -> str:
    """Creates a unified 7-day weekly file with template generators pre-populated."""
    if target_date is None:
        target_date = datetime.date.today()
        # If Sunday afternoon, default to planning next week
        if target_date.weekday() == 6:
            target_date += datetime.timedelta(days=1)

    week_dates = get_week_dates(target_date)
    if filename is None:
        filename = get_weekly_filename(target_date)

    if os.path.exists(filename) and not overwrite:
        print(
            f"Weekly file '{filename}' already exists. Use --eval or open in VS Code. (Pass --overwrite to recreate)"
        )
        return filename

    # Default templates if none provided
    if not templates:
        templates = ["school"] if os.path.exists(SCHOOL_ROUTINE) else []

    lines: list[str] = []
    year, week_num, _ = target_date.isocalendar()
    mon_str = week_dates[0].strftime("%Y-%m-%d")
    sun_str = week_dates[-1].strftime("%Y-%m-%d")

    lines.append("=" * 80 + "\n")
    lines.append(f"WEEK {week_num:02d} ({mon_str} to {sun_str})\n")
    lines.append("Week Total: [Run evaluation to calculate]\n")
    lines.append("=" * 80 + "\n\n")

    for d in week_dates:
        weekday_idx = d.weekday()
        w_short = WEEKDAYS[weekday_idx]
        w_full = WEEKDAY_FULL[weekday_idx]
        d_str = d.strftime("%Y-%m-%d")

        lines.append(
            f"=== {w_full} ({d_str}) "
            + "=" * max(1, 80 - len(w_full) - len(d_str) - 8)
            + "\n"
        )
        lines.append("# [07:30 - --:-- | Evaluating... | Status: PENDING]\n")
        if not no_daily:
            lines.append("{daily:morning}\n")

        # Inject from all passed routine template generators
        for tpl in templates:
            day_lines = generate_day_lines_from_source(
                tpl, d_str, w_short, expand=expand
            )
            lines.extend(day_lines)

        # Pre-populate default workout cadence if strength routine exists and not already in templates
        if "strength" not in templates and w_short in ["mon", "wed", "fri"]:
            lines.append("S + C |strength| [25]*2\n")

        # Weekend defaults
        if w_short == "sun":
            lines.append("meal prep [1h30]\n")
            lines.append("weekly retro & planning [45]\n")

        if not no_daily:
            lines.append("{daily:night}\n")

        lines.append("\n")

    with open(filename, "w") as f:
        f.writelines(lines)

    tpl_summary = ", ".join(templates) if templates else "defaults"
    print(f"Created weekly plan: {filename} (seeded with: {tpl_summary})")
    evaluate_weekly_file(filename)
    return filename


def evaluate_weekly_file(filename: str) -> bool:
    """Evaluates each day in the weekly file and updates status lines and header in-place."""
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return False

    with open(filename, "r") as f:
        content = f.read()

    lines = content.splitlines(keepends=True)

    # Find days and split
    day_indices = []
    for idx, line in enumerate(lines):
        match = DAY_HEADER_PATTERN.match(line)
        if match:
            day_indices.append((idx, match.group(1), match.group(2)))

    if not day_indices:
        print("No day headers ('=== Monday (YYYY-MM-DD) ===') found in file.")
        return False

    # Extract days
    total_week_mins = 0
    total_slack_mins = 0
    all_ok = True
    day_summaries: list[tuple[str, str, str]] = []

    # Keep preamble before first day
    preamble = lines[: day_indices[0][0]]

    day_blocks: list[list[str]] = []
    for i in range(len(day_indices)):
        start_idx = day_indices[i][0]
        end_idx = day_indices[i + 1][0] if i + 1 < len(day_indices) else len(lines)
        day_blocks.append(lines[start_idx:end_idx])

    updated_day_blocks: list[list[str]] = []

    for block, (_, w_name, d_str) in zip(day_blocks, day_indices):
        header_line = block[0]
        rest = block[1:]

        # Strip any existing status comment line immediately below header
        cleaned_rest: list[str] = []
        is_first_non_empty = True
        for line in rest:
            if is_first_non_empty and STATUS_LINE_PATTERN.match(line):
                is_first_non_empty = False
                continue
            if line.strip():
                is_first_non_empty = False
            cleaned_rest.append(line)

        # If date string wasn't in header, try today's date
        if not d_str:
            d_str = datetime.date.today().strftime("%Y-%m-%d")

        result = simulate_day_lines(cleaned_rest, d_str)
        status_line = f"# [{result['summary_str']}]\n"

        total_week_mins += result["total_mins"]
        total_slack_mins += result["slack_mins"]
        if "OK" not in result["status"]:
            all_ok = False

        day_summaries.append(
            (w_name, format_duration(result["total_mins"]), result["status"])
        )

        updated_block = [header_line, status_line] + cleaned_rest
        updated_day_blocks.append(updated_block)

    # Update preamble week header
    week_sched_h = total_week_mins / 60.0
    week_slack_h = total_slack_mins / 60.0
    overall_status = "ALL OK" if all_ok else "ADJUSTMENTS NEEDED"
    week_summary_str = f"Week Total: {week_sched_h:.1f}h scheduled | {week_slack_h:.1f}h slack | Status: {overall_status}\n"

    new_preamble = []
    for line in preamble:
        if line.startswith("Week Total:"):
            new_preamble.append(week_summary_str)
        else:
            new_preamble.append(line)

    final_lines = new_preamble
    for block in updated_day_blocks:
        final_lines.extend(block)

    new_content = "".join(final_lines)
    if new_content != content:
        with open(filename, "w") as f:
            f.write(new_content)

    # Print quick terminal summary
    summary_parts = [f"{w[:3]}: {dur} ({st})" for w, dur, st in day_summaries]
    print(
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Evaluated {os.path.basename(filename)}: {' | '.join(summary_parts)}"
    )
    return True


def watch_weekly_file(filename: str) -> None:
    """Watches the weekly file for saves (Cmd+S) and recalculates in-place."""
    if not os.path.exists(filename):
        print(f"Weekly file '{filename}' does not exist. Run with --init first.")
        return

    print(f"\nWatching '{filename}' for changes...")
    print("Press Cmd+S in VS Code to trigger recalculation. Press Ctrl+C to exit.\n")
    evaluate_weekly_file(filename)

    last_mtime = os.path.getmtime(filename)
    try:
        while True:
            time.sleep(0.5)
            if not os.path.exists(filename):
                continue
            cur_mtime = os.path.getmtime(filename)
            if cur_mtime > last_mtime:
                # Give file system a moment to finish write
                time.sleep(0.05)
                evaluate_weekly_file(filename)
                # Update mtime to avoid re-triggering on our own edit
                last_mtime = os.path.getmtime(filename)
    except KeyboardInterrupt:
        print("\nWatcher stopped.")


def export_daily_files(filename: str, target_date: Optional[str] = None) -> list[str]:
    """Exports tasks from the unified weekly file into individual daily/*.ans files."""
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return []

    with open(filename, "r") as f:
        lines = f.readlines()

    day_indices = []
    for idx, line in enumerate(lines):
        match = DAY_HEADER_PATTERN.match(line)
        if match:
            day_indices.append((idx, match.group(1), match.group(2)))

    if not day_indices:
        print("No day headers found to export.")
        return []

    exported_files: list[str] = []
    for i in range(len(day_indices)):
        start_idx = day_indices[i][0]
        end_idx = day_indices[i + 1][0] if i + 1 < len(day_indices) else len(lines)
        d_str = day_indices[i][2]
        if not d_str:
            continue
        if target_date and d_str != target_date:
            continue

        raw_day_lines = lines[start_idx + 1 : end_idx]
        task_lines = [
            line
            for line in raw_day_lines
            if not STATUS_LINE_PATTERN.match(line) and not line.startswith("=")
        ]

        # Resolve target daily path relative to project directory
        weekly_dir = os.path.dirname(os.path.abspath(filename))
        project_dir = (
            os.path.dirname(weekly_dir)
            if os.path.basename(weekly_dir) == WEEKLY_DIR
            else os.getcwd()
        )
        daily_dir = os.path.join(project_dir, "daily")
        os.makedirs(daily_dir, exist_ok=True)
        target_daily = os.path.join(daily_dir, f"{d_str}.ans")

        with open(target_daily, "w") as f:
            f.writelines(task_lines)
            f.write(f"\n{SPLITTER}\n\n")

        print(f"Exported -> {target_daily}")
        exported_files.append(target_daily)

    if exported_files:
        print(f"\nSuccessfully exported {len(exported_files)} daily file(s)!")
    return exported_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plex Weekly Planning Utility for VS Code"
    )
    parser.add_argument(
        "--init",
        nargs="?",
        const=True,
        default=False,
        metavar="ROUTINE",
        help="Initialize a new unified weekly plan file. Optionally specify a routine template (.txt) or generator (.py) (e.g., --init school or --init routines/my_generator.py)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch weekly file and re-calculate in-place on save",
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        help="One-time evaluation and update of weekly file",
    )
    parser.add_argument(
        "--export-daily",
        nargs="?",
        const=True,
        default=False,
        metavar="DATE",
        help="Export weekly plan into individual daily/*.ans files (optionally pass target date YYYY-MM-DD)",
    )
    parser.add_argument(
        "--date", type=str, default=None, help="Target date within week (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to weekly file (defaults to current week file)",
    )
    parser.add_argument(
        "--template",
        "-t",
        action="append",
        dest="templates",
        default=[],
        help="Routine template name (.txt) or generator script (.py) to pre-populate each day. Can specify multiple times.",
    )
    parser.add_argument(
        "--generator",
        "-g",
        type=str,
        dest="generator",
        default=None,
        help="Alias for --template",
    )
    parser.add_argument(
        "--macro",
        action="store_true",
        help="Keep routine template references as macros (e.g. {school:mon}) instead of expanding task lines",
    )
    parser.add_argument(
        "--no-daily",
        action="store_true",
        help="Do not include {daily:morning} and {daily:night}",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing weekly file when initializing",
    )

    args = parser.parse_args()

    ref_date = datetime.date.today()
    if args.date:
        ref_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()

    target_file = args.file if args.file else get_weekly_filename(ref_date)

    templates = list(args.templates)
    if args.generator:
        templates.append(args.generator)
    if isinstance(args.init, str) and args.init and args.init is not True:
        templates.insert(0, args.init)

    if args.init:
        init_weekly_file(
            ref_date,
            overwrite=args.overwrite,
            templates=templates if templates else None,
            no_daily=args.no_daily,
            filename=args.file,
            expand=not args.macro,
        )
    elif args.watch:
        watch_weekly_file(target_file)
    elif args.export_daily:
        target_d = (
            args.export_daily
            if isinstance(args.export_daily, str) and args.export_daily != "True"
            else args.date
        )
        export_daily_files(target_file, target_date=target_d)
    else:
        # Default: evaluate
        if not os.path.exists(target_file):
            print(
                f"No weekly file found at '{target_file}'. Initializing new weekly file..."
            )
            init_weekly_file(
                ref_date,
                templates=templates if templates else None,
                no_daily=args.no_daily,
                filename=args.file,
                expand=not args.macro,
            )
        else:
            evaluate_weekly_file(target_file)


if __name__ == "__main__":
    main()
