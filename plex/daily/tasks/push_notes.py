"""
Defines functions for pushing notes to the google tasks
"""
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from functools import reduce
from typing import Optional, TypedDict, Union

from plex.daily.cache import load_from_cache, save_to_cache
from plex.daily.tasks.base import Task, TaskGroup, flatten_taskgroups_into_tasks
from plex.daily.tasks.config import TaskType, convert_to_string
from plex.daily.tasks.str_sections import (
    StringSection,
    TaskGroupStringSections,
    TaskStringSections,
    convert_taskgroups_to_string_sections,
    get_field_formats,
)
from plex.daily.timing.read import split_lines_across_splitter
from plex.notion_api.page import (
    DatabaseContent,
    NotionContent,
    NotionContentGroup,
    NotionSection,
    NotionType,
    add_tasks_after,
    delete_block,
    get_contents,
    update_task,
)


def sync_tasks_to_notion(
    taskgroups: list[TaskGroup], filename: str, datestr: str
) -> None:
    """Syncs with notion tasks"""
    fsections = convert_taskgroups_to_string_sections(taskgroups)
    push_tasks_to_notion(fsections, filename, datestr)


def make_regex_parenthesis_non_capturing(rstring: str) -> str:
    newstring, _ = re.subn(r"(?<!\\)\((?:\?\:)?", "(?:", rstring)
    return newstring


def pull_tasks_from_notion(datestr: str) -> list[StringSection]:
    """pulls tasks from notion and formats them into config lines.

    Args:
        datestr (str): date string.

    Returns:
        list[str]: config lines
    """
    ncontents = get_contents()
    return convert_notion_contents_to_string_sections(ncontents, datestr)


def get_update_actions():
    # update existing tasks
    # update new tasks relative to location of template that disappeared.
    pass


def push_tasks_to_notion(
    sections: list[StringSection], filename: str, datestr: str
) -> None:
    """Push notes to notion tasks"""
    # TODO: This push section needs to be integrated into new style
    cur_sections = pull_tasks_from_notion(datestr)

    # get current task, next task
    date = datetime.fromisoformat(datestr).date()

    schedule = [
        NotionContent(NotionType.heading_1, [NotionSection("", date)])
    ] + convert_section_to_notion_contents(sections)

    add_tasks_after(schedule)


def convert_section_to_notion_contents(
    sections: list[StringSection],
) -> list[NotionContent]:
    nsection = []
    for section in sections:
        if isinstance(section, TaskStringSections):
            nsection += convert_task_section_to_notion_contents(section)
        else:
            nsection += convert_taskgroup_section_to_notion_contents(section)
    return nsection


def convert_notion_contents_to_string_sections(
    ncontents: list[NotionContent], datestr: str, indent_level: int = 0
) -> list[StringSection]:
    sections = []
    fformats = [get_field_formats(i) for i in TaskType]
    start = bool(indent_level)
    for ncontent in ncontents:
        # heading
        if ncontent.ntype == NotionType.heading_1:
            if datestr != ncontent.sections[0].start_datetime.isoformat():
                break
            else:
                start = True
        if start:
            # tasks
            if ncontent.ntype == NotionType.to_do:
                # since colors might group together, accumulate content in used_content
                used_content = ""
                is_red = False
                database_content = None
                for nsection in ncontent.sections:
                    used_content += nsection.content
                    is_red = is_red or nsection.color == "red"
                    database_content = nsection.database_content or database_content

                for fformat in fformats:
                    start_diff = fformat.start_diff.replace("\\t", r"\s")
                    end_diff = fformat.end_diff.replace("\\t", r"\s")
                    for start_diff, start, end, name, stime, end_diff in re.findall(
                        (
                            rf"({make_regex_parenthesis_non_capturing(start_diff)})?"
                            + rf"({make_regex_parenthesis_non_capturing(fformat.start)})"
                            + rf"({make_regex_parenthesis_non_capturing(fformat.end)})"
                            + rf"({make_regex_parenthesis_non_capturing(fformat.name)})"
                            + rf"({make_regex_parenthesis_non_capturing(fformat.time)})"
                            + rf"({make_regex_parenthesis_non_capturing(end_diff)})?"
                        ),
                        used_content,
                    ):
                        sections.append(
                            TaskStringSections(
                                start_diff=start_diff.replace(" ", "\t") or "\t",
                                indentation="\t" * indent_level,
                                start=start,
                                end=end,
                                name=name,
                                uuid=database_content.uuid,
                                time=stime,
                                end_diff=end_diff.replace(" ", "\t") or "\t",
                                is_overlap=is_red,
                                children=convert_notion_contents_to_string_sections(
                                    ncontent.children,
                                    datestr=datestr,
                                    indent_level=indent_level + 1,
                                ),
                                notion_uuid=ncontent.notion_uuid,
                            ).validate()
                        )

            # taskgroups
            if ncontent.ntype == NotionType.paragraph:
                if not ncontent.sections or not ncontent.sections[0].content:
                    sections.append(
                        TaskGroupStringSections(
                            is_break=True, notion_uuid=ncontent.notion_uuid
                        )
                    )
                elif ncontent.sections[0].color == "blue":
                    sections.append(
                        TaskGroupStringSections(
                            indentation="\t" * indent_level,
                            user_specified_start_or_end=ncontent.sections[0].content
                            + "\n",
                            notion_uuid=ncontent.notion_uuid,
                        )
                    )
                else:
                    sections.append(
                        TaskGroupStringSections(
                            note=ncontent.sections[0].content + "\n",
                            notion_uuid=ncontent.notion_uuid,
                        )
                    )
    return sections


def convert_taskgroup_section_to_notion_contents(
    section: TaskGroupStringSections,
) -> list[NotionContent]:
    notion_sections = [
        NotionSection(section.user_specified_start_or_end, color="blue"),
        NotionSection(section.note.replace("\n", ""), color="gray"),
    ]

    notion_sections = [nsection for nsection in notion_sections if nsection.content]

    if section.is_break:
        notion_sections.append(NotionSection(""))

    contents = []
    for nsection in notion_sections:
        if nsection.content.endswith("\n"):
            nsection.content = nsection.content.replace("\n", "")
        contents.append(NotionContent(NotionType.paragraph, sections=[nsection]))
    return contents


def convert_task_section_to_notion_contents(
    section: TaskStringSections,
) -> list[NotionContent]:

    # if section.notes:
    #     notes = [
    #         # TODO: Make these notes more comprehensive
    #         NotionContent(
    #             NotionType.paragraph,
    #             sections=[
    #                 NotionSection(note.replace("\n", ""), color="brown")
    #             ],
    #         )
    #         for note in section.notes
    #     ]
    #     print(notes)

    database_content = DatabaseContent(name=section.name, uuid=section.uuid)

    notion_sections = [
        # NotionSection(section.start_diff.replace("\t", " ")
        #               , color="green"), # remove initial start space for UX
        NotionSection(section.start, color="red" if section.is_overlap else "brown"),
        NotionSection(section.end, color="red" if section.is_overlap else "brown"),
        NotionSection(
            section.name,
            color="red" if section.is_overlap else "default",
            database_content=database_content,
        ),
        NotionSection(section.time, color="red" if section.is_overlap else "gray"),
        NotionSection(section.end_diff.replace("\t", " "), color="green"),
    ]
    for nsection in notion_sections:
        if nsection.content.endswith("\n"):
            nsection.content = nsection.content.replace("\n", "")

    return [
        NotionContent(
            NotionType.to_do,
            sections=notion_sections,
            children=convert_section_to_notion_contents(section.children),
        )
    ]


# notes = re.findall(r"(\t*-\s?.+)", section.notes)
# notes = []
# for note in section.notes.split("\n"):
#     if not note.strip():
#         continue
#     if note.startswith("\t"):
#         notes.append(note[1:])
#     else:
#         notes.append(note)

# if notes:
#     notes = [ # TODO: Synced block for notes.
#         NotionContent(
#             NotionType.paragraph,
#             sections=[
#                 NotionSection(section.indentation + "\t" + note, color="brown")
#             ],
#         )
#         for note in notes
#     ]


# def update_task_set(
#     heading: NotionContent,
#     next_task: NotionContentGroup,
#     current_tasks: list[NotionContentGroup]
# ):
#     """Will update a set of tasks under the form of:

#     # heading
#     next task
#     ## task_name
#     [ ] todo 1
#     [ ] todo 2

#     will also modify the input in place with proper uuids if not specified
#     """
#     children = []
#     if update_task(heading) is None: # create new
#         children += [heading, next_task] + current_tasks
#     else:
#         if update_task(next_task) is None:
#             children.append(next_task)
#         children += [
#             ctask for ctask in current_tasks
#             if update_task(ctask) is None
#         ]
#     add_tasks_after(children)
