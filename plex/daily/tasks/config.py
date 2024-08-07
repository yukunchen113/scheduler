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
from plex.daily.tasks.base import TaskType
from plex.daily.unique_id import PATTERN_UUID

OVERLAP_COLOR = "91m"


def get_task_line_format(task_type: TaskType = TaskType.regular):
    task_duration = rf"\(({TIMEDELTA_FORMAT})\)"
    if task_type == TaskType.deletion_request:
        task_duration = "\((-)\)"
    return (
        rf"((?:\+|-){TIMEDELTA_FORMAT})?"  # start diff
        rf"\t(\t+)?(?:\033\[{OVERLAP_COLOR})?"  # overlap start
        rf"({TIME_FORMAT})-({TIME_FORMAT}):"  # time range
        rf"\t(.+) "  # task description
        + task_duration
        + rf"(?:\033\[0m)?"  # task duration  # overlap end
        rf"\t?((?:\+|-){TIMEDELTA_FORMAT})?"  # end diff
    )


LINE_TYPE = Union[None, Task, datetime, str]


def convert_task_to_string(
    task: Task, subtask_level: int = 0, overlap_time: Optional[datetime] = None
) -> str:
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
    if overlap_time is not None and overlap_time < task.end:
        wc_begin, wc_end = f"\033[{OVERLAP_COLOR}", "\033[0m"
    output = (
        f"{start_diff}\t{subtask_indentation}"
        f"{wc_begin}"
        f"{start_time}-{end_time}:"
        f"\t{task.name} |{task.uuid}| ({process_mins_to_timedelta(task.time)})"
        f"{wc_end}"
        f"\t{end_diff}\n"
    )
    output += task.notes
    output += convert_taskgroups_to_string(
        task.subtaskgroups, subtask_level + 1, overlap_time
    )
    return output


def convert_taskgroups_to_string(
    taskgroups: list[TaskGroup],
    subtask_level: int = 0,
    default_overlap_time: Optional[datetime] = None,
) -> str:
    output = []
    for tgidx, taskgroup in enumerate(taskgroups):
        string = ""
        if taskgroup.user_specified_start is not None:
            string += (
                "\t" * subtask_level
                + taskgroup.user_specified_start.strftime("%-H:%M")
                + "\n"
            )
        for task in taskgroup.tasks:
            overlap_time = default_overlap_time
            if tgidx < len(taskgroups) - 1:
                # see if task is overlapping between intervals
                if overlap_time:
                    overlap_time = min(taskgroups[tgidx + 1].start, overlap_time)
                else:
                    overlap_time = taskgroups[tgidx + 1].start
            task_str = convert_task_to_string(task, subtask_level, overlap_time)
            string += task_str

        for note in taskgroup.notes:
            string += note

        if taskgroup.user_specified_end is not None:
            string += (
                "\t" * subtask_level
                + taskgroup.user_specified_end.strftime("%-H:%M")
                + "\n"
            )
        output.append(string)
    return "\n".join(output)


def write_taskgroups(taskgroups: list[TaskGroup], filename: str) -> None:
    with open(filename) as f:
        lines = f.readlines()
    towrite = convert_taskgroups_to_lines(taskgroups, lines)
    with open(filename, "w") as f:
        for line in towrite:
            f.write(line)


def convert_taskgroups_to_lines(
    taskgroups: list[TaskGroup], lines: list[str]
) -> list[str]:
    towrite = []
    if taskgroups:
        for line in lines:
            if line.startswith(SPLITTER):
                break
            if not line.endswith("\n"):
                line += "\n"
            towrite.append(line)
        towrite.append(f"{SPLITTER}\n\n")

        # get tasks
        towrite.append(convert_taskgroups_to_string(taskgroups))
    return towrite


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


def split_desc_and_uuid(raw_description: str):
    id_from_desc = re.findall(rf"\|((?:{PATTERN_UUID})+:[0-9]+)\|", raw_description)

    task_uuid = None
    if id_from_desc:
        # get from raw description
        task_uuid = id_from_desc[0]

    task_description = re.findall(
        rf"([^\|]+)(?:\|(?:{PATTERN_UUID})+:[0-9]+\|)?", raw_description
    )[0].strip()
    return task_description, task_uuid


def process_task_line(
    line: str, task_type: TaskType = TaskType.regular
) -> tuple[Optional[Task], int]:
    matches = re.findall(
        get_task_line_format(task_type),
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
    if task_type == TaskType.deletion_request:
        minutes = -1
    else:
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

    # process uuid
    task_des, task_uuid = split_desc_and_uuid(task_des)

    return Task(
        name=task_des,
        time=minutes,
        start=start,
        end=end,
        start_diff=start_diff,
        end_diff=end_diff,
        uuid=task_uuid,
    ), len(subtask_tabs)


def _process_taskgroups(
    lines_with_level: list[tuple[LINE_TYPE, int, str]]
) -> list[TaskGroup]:
    sublines_with_level: list[tuple[LINE_TYPE, int, str]] = []

    taskgroups: list[TaskGroup] = []
    start, start_line = None, ""
    tasks: list[Task] = []
    notes = ""
    taskgroup_notes = []

    for item, level, orig_line in lines_with_level:
        if level:
            # accumulate sublines
            if tasks:
                sublines_with_level.append((item, level - 1, orig_line))
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
                start, start_line = item, orig_line
            else:
                # clear the end of this task group
                tasks[-1] = dataclasses.replace(
                    tasks[-1],
                    subtaskgroups=_process_taskgroups(sublines_with_level),
                    notes=notes,
                )

                taskgroups.append(
                    TaskGroup(
                        tasks,
                        user_specified_start=start,
                        user_specified_end=item,
                        notes=taskgroup_notes,
                    )
                )
                notes = ""
                sublines_with_level = []

                # set up new taskgroup
                tasks = []
                taskgroup_notes = []
                start, start_line = None, ""

        elif item is None:
            if tasks:
                tasks[-1] = dataclasses.replace(
                    tasks[-1],
                    subtaskgroups=_process_taskgroups(sublines_with_level),
                    notes=notes,
                )
            if tasks or taskgroup_notes or start:
                if not tasks and start:
                    start, taskgroup_notes = None, [start_line] + taskgroup_notes
                taskgroups.append(
                    TaskGroup(tasks, user_specified_start=start, notes=taskgroup_notes)
                )
                sublines_with_level = []
                notes = ""
            assert not sublines_with_level
            tasks = []
            taskgroup_notes = []
            start, start_line = None, ""

        elif isinstance(item, str):
            if tasks:
                notes += item
            else:
                taskgroup_notes.append(item)

    if tasks:
        tasks[-1] = dataclasses.replace(
            tasks[-1],
            subtaskgroups=_process_taskgroups(sublines_with_level),
            notes=notes,
        )

    if tasks or taskgroup_notes:
        if not tasks and start or start:
            start, taskgroup_notes = None, [start_line] + taskgroup_notes
        taskgroups.append(
            TaskGroup(tasks, user_specified_start=start, notes=taskgroup_notes)
        )

    return taskgroups


def process_taskgroups_from_lines(
    lines: list[str], default_datetime: Optional[datetime] = None
) -> list[TaskGroup]:
    # create tasks
    lines_with_level: list[tuple[LINE_TYPE, int]] = []

    # gather lines
    level = 0
    for line in lines:
        task, subtask_level = process_task_line(line)
        if task is not None:
            lines_with_level.append((task, subtask_level, line))
            level = subtask_level
        elif re.match(TIME_FORMAT, line.strip()) is not None:
            num_tabs, specified_time_str = re.findall(
                r"(\t+)?({0})".format(TIME_FORMAT), line
            )[0]
            specified_time = process_time_to_datetime(
                specified_time_str, default_datetime
            )
            lines_with_level.append((specified_time, len(num_tabs), line))
            level = len(num_tabs)
        elif not line.strip():
            lines_with_level.append((None, -1, line))
        else:
            lines_with_level.append((line, level, line))

    # assign levels to everything
    level = 0
    for idx, (item, clevel, line) in list(enumerate(lines_with_level))[::-1]:
        level = clevel if clevel >= 0 else level
        lines_with_level[idx] = (item, level, line)

    # process taskgroups
    return _process_taskgroups(lines_with_level)


def read_taskgroups(
    filename: str, default_datetime: Optional[datetime] = None
) -> list[TaskGroup]:
    # gets lines after split
    return process_taskgroups_from_lines(
        get_lines_after_splitter(filename), default_datetime
    )
