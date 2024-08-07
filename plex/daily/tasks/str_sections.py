import dataclasses
import re
from datetime import datetime
from typing import Optional, TypedDict, Union

from plex.daily.config_format import (
    TIME_FORMAT,
    TIMEDELTA_FORMAT,
    process_mins_to_timedelta,
)
from plex.daily.tasks import Task, TaskGroup
from plex.daily.tasks.base import TaskType
from plex.daily.unique_id import PATTERN_UUID
from plex.transform.base import TRANSFORM, LineSection, Metadata, TransformStr

OVERLAP_COLOR = "91m"


@dataclasses.dataclass(frozen=True)
class TaskStringSections:
    start_diff: str
    indentation: str
    start: str
    end: str
    name: str
    uuid: str
    time: str
    end_diff: str

    # metadata
    notes: list[str] = dataclasses.field(default_factory=list)
    is_overlap: bool = False
    children: list = dataclasses.field(default_factory=list)

    # addition uuids for various output formats
    notion_uuid: Optional[str] = None
    source_str: Optional[TransformStr] = None
    is_source_timing: bool = False

    def validate(self):
        formats = [get_field_formats(ttype) for ttype in TaskType]
        assert any(
            re.fullmatch(fformat.start_diff, self.start_diff) for fformat in formats
        )
        assert any(
            re.fullmatch(fformat.indentation, self.indentation) for fformat in formats
        )
        assert any(re.fullmatch(fformat.start, self.start) for fformat in formats)
        assert any(re.fullmatch(fformat.end, self.end) for fformat in formats)
        assert any(re.fullmatch(fformat.name, self.name) for fformat in formats)
        assert any(re.fullmatch(fformat.uuid, self.uuid) for fformat in formats)
        assert any(re.fullmatch(fformat.time, self.time) for fformat in formats)
        assert any(re.fullmatch(fformat.end_diff, self.end_diff) for fformat in formats)
        return self


def get_field_formats(task_type: TaskType = TaskType.regular) -> TaskStringSections:
    task_duration = rf"\s?\(({TIMEDELTA_FORMAT})\)"
    if task_type == TaskType.deletion_request:
        task_duration = r"\s?\((-)\)"
    return TaskStringSections(
        start_diff=rf"((?:\+|-){TIMEDELTA_FORMAT})?\t",
        indentation=r"\t*",
        start=rf"({TIME_FORMAT})",
        end=rf"-({TIME_FORMAT}):\t",
        name=rf"(.+) ",
        uuid=rf"\|((?:{PATTERN_UUID})+:[0-9]+)\|",
        time=task_duration,
        end_diff=rf"\t?((?:\+|-){TIMEDELTA_FORMAT})?",
    )


@dataclasses.dataclass(frozen=True)
class TaskGroupStringSections:
    note: str = ""
    indentation: str = ""
    user_specified_start_or_end: str = ""
    is_break: bool = False

    # addition uuids for various output formats
    notion_uuid: Optional[str] = None
    source_str: Optional[TransformStr] = None
    is_source_timing: bool = False


StringSection = Union[TaskGroupStringSections, TaskStringSections]


def convert_task_to_string_sections(
    task: Task, subtask_level: int = 0, overlap_time: Optional[datetime] = None
) -> list[TaskStringSections]:
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

    output = [
        TaskStringSections(
            start_diff=f"{start_diff}\t",
            indentation=f"{subtask_indentation}",
            start=f"{start_time}",
            end=f"-{end_time}:\t",
            name=f"{task.name} ",
            uuid=f"|{task.uuid}|",
            time=f" ({process_mins_to_timedelta(task.time)})",
            end_diff=f"\t{end_diff}",
            notes=[
                TaskGroupStringSections(
                    note=f"{subtask_indentation}\t\t{note}",
                    source_str=note,
                )
                for note in task.notes
            ],
            is_overlap=overlap_time is not None and overlap_time < task.end,
            children=convert_taskgroups_to_string_sections(
                task.subtaskgroups, subtask_level + 1, overlap_time
            ),
            source_str=task.source_str,
            is_source_timing=task.is_source_timing,
        ).validate()
    ]
    return output


def convert_taskgroups_to_string_sections(
    taskgroups: list[TaskGroup],
    subtask_level: int = 0,
    default_overlap_time: Optional[datetime] = None,
) -> list[StringSection]:
    output = []
    for tgidx, taskgroup in enumerate(taskgroups):
        if taskgroup.user_specified_start:
            output.append(
                TaskGroupStringSections(
                    indentation=subtask_level * "\t",
                    user_specified_start_or_end=(
                        taskgroup.user_specified_start.strftime("%-H:%M") + "\n"
                    ),
                    source_str=taskgroup.user_specified_start_source_str,
                    is_source_timing=taskgroup.is_user_specified_start_source_str_timing,
                )
            )

        if taskgroup.tasks:
            for task in taskgroup.tasks:
                overlap_time = default_overlap_time
                if tgidx < len(taskgroups) - 1:
                    # see if task is overlapping between intervals
                    if taskgroups[tgidx + 1].start:
                        if overlap_time:
                            overlap_time = min(
                                taskgroups[tgidx + 1].start, overlap_time
                            )
                        else:
                            overlap_time = taskgroups[tgidx + 1].start
                output += convert_task_to_string_sections(
                    task, subtask_level, overlap_time
                )

        if taskgroup.notes:
            output += [
                TaskGroupStringSections(note=note, source_str=note)
                for note in taskgroup.notes
            ]

        if taskgroup.user_specified_end:
            output.append(
                TaskGroupStringSections(
                    indentation=subtask_level * "\t",
                    user_specified_start_or_end=(
                        taskgroup.user_specified_end.strftime("%-H:%M") + "\n"
                    ),
                    source_str=taskgroup.user_specified_end_source_str,
                    is_source_timing=taskgroup.is_user_specified_end_source_str_timing,
                )
            )
        if tgidx < len(taskgroups) - 1:  # reduce unnecessary break at end of taskgroups
            output.append(TaskGroupStringSections(is_break=True))

    return output


def flatten_string_sections(sections: list[StringSection]) -> list[StringSection]:
    output = []
    for section in sections:
        output.append(section)
        if isinstance(section, TaskStringSections):
            output += flatten_string_sections(section.notes)
            output += flatten_string_sections(section.children)
    return output
