import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pprint import pformat

from plex.daily.calendar import (
    update_calendar_with_taskgroups,
    update_calendar_with_tasks,
)
from plex.daily.preprocess import apply_preprocessing
from plex.daily.tasks import (
    DEFAULT_START_TIME,
    TaskGroup,
    flatten_taskgroups_into_tasks,
)
from plex.daily.tasks.config import (
    convert_string_section_to_config_str,
    convert_taskgroups_to_lines,
    process_taskgroups_from_lines,
    read_taskgroups,
    write_taskgroups,
)
from plex.daily.tasks.logic import (
    calculate_times_in_taskgroup_list,
    get_taskgroups_from_timing_configs,
    sync_taskgroups_with_timing,
)
from plex.daily.tasks.push_notes import pull_tasks_from_notion, sync_tasks_to_notion
from plex.daily.tasks.str_sections import flatten_string_sections
from plex.daily.template import update_templates
from plex.daily.timing import get_timing_from_file
from plex.daily.timing.process import get_timing_from_lines
from plex.daily.timing.read import split_lines_across_splitter, split_splitter_and_tasks
from plex.transform.base import TRANSFORM, LineSection, Metadata

CACHE_FILE = "cache_files/calendar_cache.pickle"


class TaskSource(Enum):
    FILE = "file"
    NOTION = "notion"


def process_daily_file(
    datestr: str, filename: str, source: TaskSource = TaskSource.FILE
) -> None:
    """Main entry point to processing the daily file

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """

    with open(filename) as file:
        lines = file.readlines()
    new_lines = process_daily_lines(datestr, lines, source)
    with open(filename, "w") as f:
        for line in new_lines:
            f.write(line)
    if source == TaskSource.NOTION:
        sync_tasks_to_notion(datestr)


def process_auto_update(
    datestr: str, filename: str, source: TaskSource = TaskSource.FILE
) -> None:
    while True:
        with open(filename) as file:
            lines = file.readlines()
        new_lines = process_daily_lines(datestr, lines, source)
        with open(filename, "w") as f:
            for line in new_lines:
                f.write(line)
        if source == TaskSource.NOTION:
            sync_tasks_to_notion(datestr)
        time.sleep(0.5)


def process_daily_lines(
    datestr: str, lines: list[str], source: TaskSource = TaskSource.FILE
) -> list[str]:
    """processes the lines for file

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """
    TRANSFORM.clear()
    timing_lines, splitter_line, task_lines = split_lines_across_splitter(
        lines, is_separate_splitter=True
    )
    timing_lines = [
        TRANSFORM.append(line, Metadata(section=LineSection.timing))
        for line in timing_lines
    ]
    if splitter_line:
        splitter_line[0] = TRANSFORM.append(
            splitter_line[0],
            Metadata(
                section=LineSection.neither,
            ),
        )

    if source == TaskSource.NOTION:
        notion_sections = pull_tasks_from_notion(datestr)
        if notion_sections is not None:
            task_lines = []
            for section in flatten_string_sections(notion_sections):
                task_line = convert_string_section_to_config_str(section)
                if task_line is None:
                    raise ValueError(f"Invalid string section unrecognized: {section}")
                task_lines.append(
                    TRANSFORM.append(
                        task_line,
                        Metadata(
                            section=LineSection.task, notion_uuid=section.notion_uuid
                        ),
                    )
                )
    else:
        task_lines = [
            TRANSFORM.append(task_line, Metadata(section=LineSection.task))
            for task_line in task_lines
        ]
    TRANSFORM.validate(timing_lines + splitter_line + task_lines)

    date = datetime.strptime(datestr, "%Y-%m-%d").astimezone()
    date = date.replace(**DEFAULT_START_TIME)

    timing_lines, task_lines = apply_preprocessing(
        timing_lines, task_lines, datestr=datestr
    )
    TRANSFORM.validate(timing_lines + splitter_line + task_lines)

    timing_lines = update_templates(timing_lines, datestr=datestr, is_main_file=True)
    TRANSFORM.validate(timing_lines + splitter_line + task_lines)

    timings, timing_lines = get_timing_from_lines(timing_lines, date)
    TRANSFORM.validate(timing_lines + splitter_line + task_lines)
    read_tasks = process_taskgroups_from_lines(task_lines, date)
    if not read_tasks:
        taskgroups = get_taskgroups_from_timing_configs(timings)
        taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
    else:
        taskgroups = sync_taskgroups_with_timing(timings, read_tasks, date)

    new_lines = convert_taskgroups_to_lines(
        taskgroups, timing_lines + splitter_line + task_lines, is_skip_transform=False
    )
    TRANSFORM.validate(new_lines)
    return new_lines


def sync_tasks_to_calendar(
    datestr: str, filename: str, push_only: bool = False
) -> None:
    """Syncs tasks to calendar.

    Args:
        datestr (str): date in the form of %Y-%m-%d
        filename (str): filename for daily processing
    """
    date = datetime.strptime(datestr, "%Y-%m-%d").astimezone()
    date = date.replace(**DEFAULT_START_TIME)
    while True:
        taskgroups = read_taskgroups(filename, date)
        taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
        if push_only:
            tasks = flatten_taskgroups_into_tasks(taskgroups)
            update_calendar_with_tasks(tasks, datestr)
            break
        else:
            taskgroups = update_calendar_with_taskgroups(taskgroups, datestr)
            if taskgroups:
                # recalculate taskgroups
                taskgroups = calculate_times_in_taskgroup_list(taskgroups, date)
                write_taskgroups(taskgroups, filename)
            else:
                time.sleep(10)
