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
from plex.daily.tasks.config import (
    TaskType,
    convert_string_section_to_config_str,
    convert_to_string,
)
from plex.daily.tasks.str_sections import (
    StringSection,
    TaskGroupStringSections,
    TaskStringSections,
    convert_config_str_to_string_section,
    convert_taskgroups_to_string_sections,
    flatten_string_sections,
    get_field_formats,
    make_regex_parenthesis_non_capturing,
    unflatten_string_sections,
)
from plex.daily.timing.read import split_lines_across_splitter, split_splitter_and_tasks
from plex.notion_api.page import (
    DatabaseContent,
    NotionContent,
    NotionContentGroup,
    NotionSection,
    NotionType,
    add_tasks_after,
    delete_block,
    get_block,
    get_contents,
    update_task,
)
from plex.transform.base import TRANSFORM, LineSection, Metadata


def overwrite_tasks_in_notion(datestr: str):
    notion_sections = pull_tasks_from_notion(datestr)
    if notion_sections is not None:
        print("Clearing Existing Notion Tasks...")
        for section in notion_sections:
            block = get_block(section.notion_uuid)
            if block:
                delete_block(notion_uuid=section.notion_uuid)
    sync_tasks_to_notion(datestr, force_push=True)


def sync_tasks_to_notion(datestr, force_push=False) -> None:
    """Syncs with notion tasks"""
    notion_sections = None if force_push else pull_tasks_from_notion(datestr)

    _, _, new_tasks = split_lines_across_splitter(
        TRANSFORM.construct_content(), is_separate_splitter=True
    )

    # find tasks to add, update, delete
    if notion_sections is None:
        # if first time generation, add everything
        print("Pushing Existing Notion Tasks...")
        new_sections = [
            convert_config_str_to_string_section(new_task) for new_task in new_tasks
        ]
        push_tasks_to_notion(unflatten_string_sections(new_sections), datestr)

    else:
        current_tasks = {
            section.notion_uuid: convert_string_section_to_config_str(section)
            for section in flatten_string_sections(notion_sections)
        }

        transformations = []
        for initial_state in TRANSFORM.get_initial_states():
            if initial_state == "\n":
                continue
            final_state = TRANSFORM.construct_content(focus_lines=[initial_state])
            if len(final_state) == 1 and final_state[0] == initial_state:
                continue
            notion_uuid = TRANSFORM.get_metadata(initial_state).notion_uuid
            if notion_uuid in current_tasks:
                transformations.append((notion_uuid, initial_state, final_state))

        # sort transformations based on precedence
        deletions, preprocessed, other = [], [], []
        for notion_uuid, initial_state, final_state in transformations:
            if not final_state:
                deletions.append((notion_uuid, initial_state, final_state))
            elif any(TRANSFORM.get_metadata(fs).is_preprocessed for fs in final_state):
                preprocessed.append((notion_uuid, initial_state, final_state))
            else:
                other.append((notion_uuid, initial_state, final_state))

        update_latest_representations(preprocessed)
        update_latest_representations(deletions)
        update_latest_representations(other)


def update_latest_representations(change_set):
    for notion_uuid, initial_state, final_state in change_set:
        # get latest str represetation, ignore indentation level.
        final_state_ncontent = convert_sections_to_notion_contents(
            unflatten_string_sections(
                [convert_config_str_to_string_section(fs) for fs in final_state]
            )
        )
        if (
            get_latest_str_representation(
                notion_uuid,
                len(convert_config_str_to_string_section(initial_state).indentation),
            )
            == initial_state
        ):
            print(f"Updating '{repr(initial_state)}' to '{final_state}'")
            if len(final_state_ncontent) == 1:
                update_task(final_state_ncontent[0], notion_uuid=notion_uuid)
            else:
                if final_state_ncontent:
                    add_tasks_after(final_state_ncontent, notion_uuid)
                delete_block(notion_uuid=notion_uuid)


def get_latest_str_representation(
    notion_uuid: int, indent_level: int = 0
) -> Optional[str]:
    block = get_block(notion_uuid)
    if block:
        return convert_string_section_to_config_str(
            convert_notion_contents_to_string_sections(
                [block], indent_level=indent_level
            ).pop()
        )


def pull_tasks_from_notion(datestr: str) -> list[StringSection]:
    """pulls tasks from notion and formats them into config lines.

    Args:
        datestr (str): date string.

    Returns:
        list[str]: config lines
    """
    return convert_notion_contents_to_string_sections(get_contents(), datestr)


def push_tasks_to_notion(sections: list[StringSection], datestr: str) -> None:
    """Push notes to notion tasks"""
    # get current task, next task
    date = datetime.fromisoformat(datestr).date()

    schedule = [
        NotionContent(NotionType.heading_1, [NotionSection("", date)])
    ] + convert_sections_to_notion_contents(sections)

    add_tasks_after(schedule)


def convert_sections_to_notion_contents(
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
    ncontents: list[NotionContent],
    datestr: Optional[str] = None,
    indent_level: int = 0,
) -> Optional[list[StringSection]]:
    sections = None if datestr is not None else []
    fformats = [get_field_formats(i) for i in TaskType]
    for ncontent in ncontents:
        # heading
        if datestr is not None and ncontent.ntype == NotionType.heading_1:
            if (
                datestr != ncontent.sections[0].start_datetime.isoformat()
                and sections is not None
            ):
                continue
            else:
                sections = []
        if isinstance(sections, list):
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
                                name=name.rstrip() + " ",
                                uuid=database_content.uuid,
                                time=stime,
                                end_diff=end_diff.replace(" ", "\t") or "\t",
                                is_overlap=is_red,
                                children=convert_notion_contents_to_string_sections(
                                    ncontent.children,
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
        contents.append(
            NotionContent(
                NotionType.paragraph,
                sections=[nsection],
                notion_uuid=section.notion_uuid,
            )
        )
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
            children=convert_sections_to_notion_contents(section.children),
            notion_uuid=section.notion_uuid,
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
