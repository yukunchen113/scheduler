"""
Defines functions for pushing notes to the google tasks
"""
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, TypedDict

from plex.daily.cache import load_from_cache, save_to_cache
from plex.daily.tasks.base import Task, TaskGroup, flatten_taskgroups_into_tasks
from plex.daily.tasks.config import (
    TaskGroupStringSections,
    TaskStringSections,
    convert_taskgroups_to_string_sections,
)
from plex.notion_api.page import (
    NotionContent,
    NotionContentGroup,
    NotionSection,
    NotionType,
    add_tasks_after,
    delete_block,
    update_task,
)


def sync_tasks_to_notion(
    taskgroups: list[TaskGroup], filename: str, datestr: str
) -> None:
    """Syncs with notion tasks"""
    push_tasks_to_notion(taskgroups, filename, datestr)


def push_tasks_to_notion(
    taskgroups: list[TaskGroup], filename: str, datestr: str
) -> None:
    """Push notes to notion tasks"""

    # get current task, next task
    date = datetime.strptime(datestr, "%Y-%m-%d").date()

    schedule = [NotionContent(NotionType.heading_1, [NotionSection("", date)])]
    for section in convert_taskgroups_to_string_sections(taskgroups):
        if isinstance(section, TaskStringSections):
            schedule += convert_task_section_to_notion_contents(section)
        else:
            schedule += convert_taskgroup_section_to_notion_contents(section)
    add_tasks_after(schedule)


def convert_taskgroup_section_to_notion_contents(
    section: TaskGroupStringSections,
) -> list[NotionContent]:
    notion_sections = (
        [NotionSection(section.user_specified_start, color="blue")]
        + [
            NotionSection(note.replace("\n", ""), color="gray")
            for note in section.notes
        ]
        + [NotionSection(section.user_specified_end, color="blue")]
    )

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
    notion_sections = [
        NotionSection(section.start_diff + section.indentation, color="green"),
        NotionSection(
            section.start + section.end, color="red" if section.is_overlap else "brown"
        ),
        NotionSection(section.name, color="red" if section.is_overlap else "default"),
        NotionSection(section.time, color="red" if section.is_overlap else "gray"),
        NotionSection(section.end_diff, color="green"),
    ]
    for nsection in notion_sections:
        if nsection.content.endswith("\n"):
            nsection.content = nsection.content.replace("\n", "")

    # notes = re.findall(r"(\t*-\s?.+)", section.notes)
    notes = []
    for note in section.notes.split("\n"):
        if not note.strip():
            continue
        if note.startswith("\t"):
            notes.append(note[1:])
        else:
            notes.append(note)

    if notes:
        notes = [
            NotionContent(
                NotionType.paragraph,
                sections=[
                    NotionSection(section.indentation + "\t" + note, color="brown")
                ],
            )
            for note in notes
        ]

    return [NotionContent(NotionType.paragraph, sections=notion_sections)] + notes


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
