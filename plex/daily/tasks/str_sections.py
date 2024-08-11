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
OVERLAP_START_FORMAT = rf"(?:\033\[{OVERLAP_COLOR})"
OVERLAP_END_FORMAT = rf"(?:\033\[0m)"


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
    children: list["StringSection"] = dataclasses.field(default_factory=list)

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


def make_regex_parenthesis_non_capturing(rstring: str) -> str:
    newstring, _ = re.subn(r"(?<!\\)\((?:\?\:)?", "(?:", rstring)
    return newstring


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

    def validate(self):
        assert (
            sum(
                bool(i)
                for i in [
                    self.note,
                    self.user_specified_start_or_end,
                    self.is_break,
                ]
            )
            == 1
        ), f"note: {repr(self.note)}, user specified start/end: {repr(self.user_specified_start_or_end)}, is break: {repr(self.is_break)}"
        if self.user_specified_start_or_end or self.note:
            assert self.source_str
        return self


StringSection = Union[TaskGroupStringSections, TaskStringSections]


def get_task_config_str_format(task_type: TaskType = TaskType.regular) -> str:
    task_duration = rf"\(({TIMEDELTA_FORMAT})\)"
    if task_type == TaskType.deletion_request:
        task_duration = r"\((-)\)"
    formats = get_field_formats(task_type)
    return (
        formats.start_diff  # start diff
        + rf"(\t+)?(?:{OVERLAP_START_FORMAT})?"  # overlap start
        + formats.start
        + formats.end
        + formats.name
        + task_duration
        + rf"(?:{OVERLAP_END_FORMAT})?"  # overlap end
        + formats.end_diff
    )


def unflatten_string_sections(
    sections: list[StringSection], indentation_level: int = 0
):
    # best efforts
    new_sections = []
    while sections:
        subsections = []
        while sections and len(sections[0].indentation) > indentation_level:
            subsections.append(sections.pop(0))
        subsections = unflatten_string_sections(subsections, indentation_level + 1)
        if new_sections and isinstance(new_sections[-1], TaskStringSections):
            new_sections[-1] = dataclasses.replace(
                new_sections[-1], children=subsections
            )
        else:
            new_sections += subsections
        if sections:
            new_sections.append(sections.pop(0))
    return new_sections


def convert_config_str_to_string_section(line: str):
    # try all task formats
    for ttype in TaskType:
        fformat = get_field_formats(ttype)
        for (
            start_diff,
            indentation,
            overlap,
            start,
            end,
            name,
            uuid,
            stime,
            end_diff,
        ) in re.findall(
            (
                rf"(^{make_regex_parenthesis_non_capturing(fformat.start_diff)})"
                + rf"({make_regex_parenthesis_non_capturing(fformat.indentation)})"
                + rf"({OVERLAP_START_FORMAT})?"
                + rf"({make_regex_parenthesis_non_capturing(fformat.start)})"
                + rf"({make_regex_parenthesis_non_capturing(fformat.end)})"
                + rf"({make_regex_parenthesis_non_capturing(fformat.name)})"
                + rf"({make_regex_parenthesis_non_capturing(fformat.uuid)})"
                + rf"({make_regex_parenthesis_non_capturing(fformat.time)})"
                + rf"(?:{OVERLAP_START_FORMAT})?"
                + rf"({make_regex_parenthesis_non_capturing(fformat.end_diff)})?"
            ),
            line,
        ):
            return TaskStringSections(
                start_diff=start_diff,
                indentation=indentation,
                start=start,
                end=end,
                name=name,
                uuid=uuid,
                time=stime,
                end_diff=end_diff,
                is_overlap=bool(overlap),
            ).validate()

    # Taskgroup string section
    if line == "\n":
        return TaskGroupStringSections(is_break=True).validate()

    for indentation, content in re.findall(r"(\t*)(.*)", line):
        metadata = TRANSFORM.get_metadata(line)
        if (
            metadata is not None
            and metadata.line_info is not None
            and not metadata.line_info.is_taskgroup_note
        ):
            return TaskGroupStringSections(
                indentation=indentation, user_specified_start_or_end=content
            ).validate()
        else:
            return TaskGroupStringSections(note=indentation + content).validate()


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
                ).validate()
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
                ).validate()
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
                TaskGroupStringSections(note=note, source_str=note).validate()
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
                ).validate()
            )
        if tgidx < len(taskgroups) - 1:  # reduce unnecessary break at end of taskgroups
            output.append(TaskGroupStringSections(is_break=True).validate())

    return output


def flatten_string_sections(sections: list[StringSection]) -> list[StringSection]:
    output = []
    if not sections:
        return output
    for section in sections:
        output.append(section)
        if isinstance(section, TaskStringSections):
            output += flatten_string_sections(section.notes)
            output += flatten_string_sections(section.children)
    return output


def convert_string_section_to_config_str(section: StringSection) -> Optional[str]:
    output = None
    if isinstance(section, TaskStringSections):
        wc_begin = wc_end = ""
        if section.is_overlap:
            wc_begin, wc_end = f"\033[{OVERLAP_COLOR}", "\033[0m"
        output = (
            section.start_diff
            + section.indentation
            + wc_begin
            + section.start
            + section.end
            + section.name
            + section.uuid
            + (
                " "
                if not (section.uuid.endswith(" ") or section.time.startswith(" "))
                else ""
            )
            + section.time
            + wc_end
            + section.end_diff
            + "\n"
        )
    elif isinstance(section, TaskGroupStringSections):
        if section.is_break:
            output = "\n"
        else:
            output = (
                section.indentation + section.user_specified_start_or_end + section.note
            )
    assert (
        output.count("\n") == 1
    ), f"Task string spec must have exactly one newline but is {output}"
    return output
