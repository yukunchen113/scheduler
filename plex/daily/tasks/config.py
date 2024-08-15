import dataclasses
import re
from datetime import datetime
from typing import Optional, TypedDict, Union

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
from plex.daily.tasks.str_sections import (
    StringSection,
    TaskGroupStringSections,
    TaskStringSections,
    convert_string_section_to_config_str,
    convert_task_to_string_sections,
    convert_taskgroups_to_string_sections,
    flatten_string_sections,
    get_field_formats,
    get_task_config_str_format,
)
from plex.daily.unique_id import PATTERN_UUID
from plex.transform.base import TRANSFORM, LineInfo, LineSection, Metadata, TransformStr

OVERLAP_COLOR = "91m"


def convert_to_string(
    item: Union[Task, list[TaskGroup]],
    subtask_level: int = 0,
    overlap_time: Optional[datetime] = None,
    *,
    is_skip_tranform: bool = True,
) -> list[str]:
    if isinstance(item, Task):
        sections = convert_task_to_string_sections(item, subtask_level, overlap_time)
    else:
        sections = convert_taskgroups_to_string_sections(
            item, subtask_level, overlap_time
        )
    output = []
    prev_section_string = None
    for section in flatten_string_sections(sections):
        converted_str = convert_string_section_to_config_str(section)
        if converted_str is not None:
            if isinstance(section, TaskGroupStringSections) and section.is_break:
                # line breaks for Task Groups.
                prev_section_string = (
                    converted_str
                    if is_skip_tranform
                    else TRANSFORM.append(
                        converted_str,
                        metadata=Metadata(
                            section=LineSection.task,
                            line_info=LineInfo(is_spacing_element=True),
                        ),
                        add_after_content=prev_section_string,
                    )
                )
            elif (
                isinstance(section, (TaskGroupStringSections, TaskStringSections))
                and section.is_source_timing
            ):
                # new task or taskgroup item that was generated from timing.
                if prev_section_string is not None:
                    # initially created task string
                    prev_section_string = (
                        converted_str
                        if is_skip_tranform
                        else TRANSFORM.add_after(
                            section.source_str,
                            [converted_str],
                            prev_section_string,
                            metadata=Metadata(
                                section=LineSection.task,
                                line_info=LineInfo(
                                    is_taskgroup_note=isinstance(
                                        section, TaskGroupStringSections
                                    )
                                    and bool(section.note)
                                ),
                            ),
                            soft_failure=is_skip_tranform,
                        )[0]
                    )
                else:
                    prev_section_string = (
                        converted_str
                        if is_skip_tranform
                        else TRANSFORM.append(
                            converted_str,
                            metadata=Metadata(
                                section=LineSection.task,
                                line_info=LineInfo(
                                    is_taskgroup_note=isinstance(
                                        section, TaskGroupStringSections
                                    )
                                    and bool(section.note)
                                ),
                            ),
                            add_after_content=prev_section_string,
                        )
                    )
            else:
                # task or taskgroup string section to be replaced.
                prev_section_string = (
                    converted_str
                    if is_skip_tranform
                    else TRANSFORM.replace(
                        section.source_str,
                        converted_str,
                        metadata=dataclasses.replace(
                            TRANSFORM.get_metadata(section.source_str),
                            line_info=LineInfo(
                                is_taskgroup_note=isinstance(
                                    section, TaskGroupStringSections
                                )
                                and bool(section.note)
                            ),
                        ),
                    )
                )
            output.append(prev_section_string)
    return output


LINE_TYPE = Union[None, Task, datetime, str]


def write_taskgroups(taskgroups: list[TaskGroup], filename: str) -> None:
    with open(filename) as f:
        lines = f.readlines()
    towrite = convert_taskgroups_to_lines(taskgroups, lines)
    with open(filename, "w") as f:
        for line in towrite:
            f.write(line)


def convert_taskgroups_to_lines(
    taskgroups: list[TaskGroup],
    lines: Optional[list[TransformStr]] = None,
    is_skip_transform: bool = True,
) -> list[str]:
    if lines is None:
        lines = []
    towrite = []
    while lines:
        line = lines.pop(0)
        if line.startswith(SPLITTER):
            TRANSFORM.delete(line)
            break
        if not line.endswith("\n"):
            line = TRANSFORM.replace(line, line + "\n")
        towrite.append(line)
    if taskgroups:
        append_after = towrite[-1] if towrite else None
        towrite.append(
            TRANSFORM.append(f"{SPLITTER}\n\n", add_after_content=append_after)
        )

        # get tasks
        towrite += convert_to_string(taskgroups, is_skip_tranform=is_skip_transform)

        # clean up lines that weren't transformed
        for remaining_line in lines:
            if not TRANSFORM.is_updated(remaining_line):
                TRANSFORM.delete(remaining_line)
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
    id_from_desc = re.findall(get_field_formats().uuid, raw_description)

    task_uuid = None
    if id_from_desc:
        # get from raw description
        task_uuid = id_from_desc[0]

    task_description = re.findall(
        rf"([^\|]+)(?:\|(?:{PATTERN_UUID})+:[0-9]+\|)?", raw_description
    )[0].strip()
    return task_description, task_uuid


def process_task_line(
    line: TransformStr, task_type: TaskType = TaskType.regular
) -> tuple[Optional[Task], int]:
    matches = re.findall(
        get_task_config_str_format(task_type),
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
        indentation_level=len(subtask_tabs),
        source_str=line,
    ), len(subtask_tabs)


def _process_taskgroups(
    lines_with_level: list[tuple[LINE_TYPE, int, TransformStr]]
) -> list[TaskGroup]:
    sublines_with_level: list[tuple[LINE_TYPE, int, TransformStr]] = []

    taskgroups: list[TaskGroup] = []
    start, start_line = None, ""
    tasks: list[Task] = []
    notes = []
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
            if taskgroup_notes:
                if not tasks and start:
                    start, taskgroup_notes = None, [start_line] + taskgroup_notes
                    start_line = ""
                taskgroups.append(
                    TaskGroup(
                        [],
                        user_specified_start=start,
                        notes=taskgroup_notes,
                        user_specified_start_source_str=start_line or None,
                    )
                )
                taskgroup_notes = []

            if sublines_with_level:
                tasks[-1] = dataclasses.replace(
                    tasks[-1],
                    subtaskgroups=_process_taskgroups(sublines_with_level),
                    notes=notes,
                )
                notes = []
                sublines_with_level = []
            if notes:
                tasks[-1] = dataclasses.replace(
                    tasks[-1],
                    notes=notes,
                )
                notes = []
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
                        user_specified_start_source_str=start_line or None,
                        user_specified_end_source_str=orig_line or None,
                    )
                )
                notes = []
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
                    start_line = ""
                taskgroups.append(
                    TaskGroup(
                        tasks,
                        user_specified_start=start,
                        notes=taskgroup_notes,
                        user_specified_start_source_str=start_line or None,
                    )
                )
                sublines_with_level = []
                notes = []
            assert not sublines_with_level
            tasks = []
            taskgroup_notes = []
            start, start_line = None, ""

        elif isinstance(item, str):

            note = item
            if tasks and not taskgroup_notes:
                indented = re.match(r"^\t*-\s", note)
                if indented:
                    base_nind = tasks[-1].indentation_level + 1
                    max_nind = base_nind
                    if notes:
                        max_nind = (
                            base_nind
                            + len(
                                re.match(r"^\t*-\s", notes[-1])
                                .group(0)
                                .replace("- ", "")
                            )
                            + 1
                        )
                    cur_nind = len(indented.group(0).replace("- ", ""))
                    if max_nind >= cur_nind >= base_nind:
                        notes.append(TRANSFORM.replace(item, note[base_nind:]))
                        note = None
            if note:
                # clear out tasks
                if tasks:
                    tasks[-1] = dataclasses.replace(
                        tasks[-1],
                        subtaskgroups=_process_taskgroups(sublines_with_level),
                        notes=notes,
                    )
                    taskgroups.append(
                        TaskGroup(
                            tasks,
                            user_specified_start=start,
                            user_specified_start_source_str=start_line or None,
                        )
                    )
                    sublines_with_level = []
                    notes = []
                    assert not sublines_with_level
                    tasks = []
                    start, start_line = None, ""
                taskgroup_notes.append(TRANSFORM.replace(item, note))

    if tasks:
        tasks[-1] = dataclasses.replace(
            tasks[-1],
            subtaskgroups=_process_taskgroups(sublines_with_level),
            notes=notes,
        )

    if tasks or taskgroup_notes:
        if not tasks and start:
            start, taskgroup_notes = None, [start_line] + taskgroup_notes
            start_line = ""
        taskgroups.append(
            TaskGroup(
                tasks,
                user_specified_start=start,
                notes=taskgroup_notes,
                user_specified_start_source_str=start_line or None,
            )
        )

    return taskgroups


def process_taskgroups_from_lines(
    lines: list[TransformStr], default_datetime: Optional[datetime] = None
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
            TRANSFORM.delete(line)
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
