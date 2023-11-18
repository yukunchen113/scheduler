import dataclasses
import re
from datetime import datetime
from typing import Optional, Union

from plex.daily.config_format import (
    SPLITTER,
    TIME_FORMAT,
    TIMEDELTA_FORMAT,
    process_mins_to_timedelta,
    process_time_to_datetime,
    process_timedelta_to_mins,
)
from plex.daily.tasks import Task, TaskGroup

OVERLAP_COLOR = '91m'

TASK_LINE_FORMAT = (
    r"((?:\+|-){0})?\t(\t+)?(?:\033\[{2})?({1})-({1}):\t(.+) \(({0})\)(?:\033\[0m)?\t?((?:\+|-){0})?".format(
        TIMEDELTA_FORMAT, TIME_FORMAT, OVERLAP_COLOR
    )
)

LINE_TYPE = Union[None, Task, datetime, str]


def prep_tasks_section(filename: str) -> list[str]:
    towrite = []
    with open(filename) as f:
        for line in f.readlines():
            if line.startswith(SPLITTER):
                break
            if not line.endswith("\n"):
                line += "\n"
            towrite.append(line)
        towrite.append(f"{SPLITTER}\n")
    towrite.append("\n")
    return towrite


def convert_task_to_string(task: Task, subtask_level: int = 0, is_warning_color: bool = False) -> str:
    assert task.start is not None
    assert task.end is not None
    start_time = task.start.strftime("%-H:%M")
    end_time = task.end.strftime("%-H:%M")
    start_diff = (
        ""
        if task.start_diff is None
        else f'{"+" if task.start_diff>=0 else "-"}{process_mins_to_timedelta(abs(task.start_diff))}'
    )
    end_diff = (
        ""
        if task.end_diff is None
        else f'{"+" if task.end_diff>=0 else "-"}{process_mins_to_timedelta(abs(task.end_diff))}'
    )
    subtask_indentation = "\t" * subtask_level
    wc_begin = wc_end = ""
    if is_warning_color:
        wc_begin, wc_end = f"\033[{OVERLAP_COLOR}", '\033[0m'
    output = (
        f"{start_diff}\t{subtask_indentation}"
        f"{wc_begin}"
        f"{start_time}-{end_time}:"
        f"\t{task.name} ({process_mins_to_timedelta(task.time)})"
        f"{wc_end}"
        f"\t{end_diff}\n"
    )
    output += task.notes
    output += convert_taskgroups_to_string(
        task.subtaskgroups, subtask_level + 1)
    return output


def convert_taskgroups_to_string(
    taskgroups: list[TaskGroup], subtask_level: int = 0
) -> str:
    output = []
    for tgidx, taskgroup in enumerate(taskgroups):
        string = ""
        if taskgroup.user_specified_start is not None:
            string += "\t" * subtask_level + \
                taskgroup.user_specified_start.strftime("%-H:%M") + "\n"
        for task in taskgroup.tasks:
            is_overlapped_task = False
            if tgidx < len(taskgroups)-1:
                # see if task is overlapping between intervals
                is_overlapped_task = taskgroups[tgidx+1].start < task.end
            task_str = convert_task_to_string(
                task, subtask_level, is_overlapped_task)
            string += task_str
        if taskgroup.user_specified_end is not None:
            string += "\t" * subtask_level + \
                taskgroup.user_specified_end.strftime("%-H:%M") + "\n"
        output.append(string)
    return "\n".join(output)


def write_taskgroups(taskgroups: list[TaskGroup], filename: str) -> None:
    towrite = prep_tasks_section(filename)
    # get tasks
    towrite.append(convert_taskgroups_to_string(taskgroups))
    # write
    with open(filename, "w") as f:
        for line in towrite:
            f.write(line)


def get_lines_after_splitter(filename: str) -> list[str]:
    lines: list[str] = []
    is_splitter_exist: bool = False
    with open(filename) as f:
        for line in f.readlines():
            if line.startswith(SPLITTER):
                is_splitter_exist = True
                lines = []
            else:
                lines.append(line)
    if not is_splitter_exist:
        return []
    return lines


def process_task_line(line: str) -> tuple[Optional[Task], int]:
    matches = re.findall(
        TASK_LINE_FORMAT,
        line,
    )
    if not matches:
        return None, -1
    (
        start_diff,
        subtask_tabs,
        start_time,
        end_time,
        task_des,
        minutes,
        end_diff,
    ) = matches[0]
    minutes = process_timedelta_to_mins(minutes)
    start = process_time_to_datetime(start_time)
    end = process_time_to_datetime(end_time)
    start_diff = (
        None
        if start_diff == ""
        else process_timedelta_to_mins(start_diff[1:]) * int(start_diff[0] + "1")
    )
    end_diff = (
        None
        if end_diff == ""
        else process_timedelta_to_mins(end_diff[1:]) * int(end_diff[0] + "1")
    )
    return Task(
        name=task_des,
        time=minutes,
        start=start,
        end=end,
        start_diff=start_diff,
        end_diff=end_diff,
    ), len(subtask_tabs)


def _process_taskgroups(
    lines_with_level: list[tuple[LINE_TYPE, int]]
) -> list[TaskGroup]:
    sublines_with_level: list[tuple[LINE_TYPE, int]] = []

    taskgroups: list[TaskGroup] = []
    start, end = None, None
    tasks: list[Task] = []
    notes = ""
    for item, level in lines_with_level:
        if level:
            # accumulate sublines
            if tasks:
                sublines_with_level.append((item, level - 1))
            # ignore subtasks that don't have an associated task
            # even if they have start and end diffs on them.
            continue
        if isinstance(item, Task):
            if sublines_with_level:
                tasks[-1] = dataclasses.replace(
                    tasks[-1],
                    subtaskgroups=_process_taskgroups(sublines_with_level),
                    notes=notes,
                )
                notes = ""
                sublines_with_level = []
            if notes:
                tasks[-1] = dataclasses.replace(
                    tasks[-1],
                    notes=notes,
                )
                notes = ""
            tasks.append(item)
        elif isinstance(item, datetime):
            if not tasks:
                # start
                start, end = item, None
            else:
                # clear the end of this task group
                tasks[-1] = dataclasses.replace(
                    tasks[-1],
                    subtaskgroups=_process_taskgroups(sublines_with_level),
                    notes=notes,
                )
                taskgroups.append(
                    TaskGroup(tasks, user_specified_start=start, user_specified_end=item))
                notes = ""
                sublines_with_level = []

                # set up new taskgroup
                tasks = []
                start, end = end, None

        elif item is None:
            if tasks:
                tasks[-1] = dataclasses.replace(
                    tasks[-1],
                    subtaskgroups=_process_taskgroups(sublines_with_level),
                    notes=notes,
                )
                taskgroups.append(
                    TaskGroup(tasks, user_specified_start=start, user_specified_end=end))
                sublines_with_level = []
                notes = ""
            assert not sublines_with_level
            tasks = []
            start, end = None, None
        elif isinstance(item, str):
            if tasks:
                notes += item

    if tasks:
        tasks[-1] = dataclasses.replace(
            tasks[-1],
            subtaskgroups=_process_taskgroups(sublines_with_level),
            notes=notes,
        )
        taskgroups.append(
            TaskGroup(tasks, user_specified_start=start, user_specified_end=end))
    return taskgroups


def read_taskgroups(filename: str, default_datetime: Optional[datetime] = None) -> list[TaskGroup]:
    # gets lines after split
    lines = get_lines_after_splitter(filename)
    # create tasks
    lines_with_level: list[tuple[LINE_TYPE, int]] = []

    # gather lines
    level = 0
    for line in lines:
        task, subtask_level = process_task_line(line)
        if task is not None:
            lines_with_level.append((task, subtask_level))
            level = subtask_level
        elif re.match(TIME_FORMAT, line.strip()) is not None:
            num_tabs, specified_time_str = re.findall(
                r"(\t+)?({0})".format(TIME_FORMAT), line
            )[0]
            specified_time = process_time_to_datetime(
                specified_time_str, default_datetime)
            lines_with_level.append((specified_time, len(num_tabs)))
            level = len(num_tabs)
        elif not line.strip():
            lines_with_level.append((None, -1))
        else:
            lines_with_level.append((line, level))
    # assign levels to everything
    level = 0
    for idx, (item, clevel) in list(enumerate(lines_with_level))[::-1]:
        level = clevel if clevel >= 0 else level
        lines_with_level[idx] = (item, level)
    # process taskgroups
    return _process_taskgroups(lines_with_level)
