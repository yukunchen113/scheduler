"""
Defines functions for pushing notes to the google tasks
"""
import queue
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from functools import reduce
from typing import Optional, TypedDict, Union

from notion_client.errors import APIResponseError

from plex.daily.cache import load_from_cache, save_to_cache
from plex.daily.tasks.base import Task, TaskGroup, flatten_taskgroups_into_tasks
from plex.daily.tasks.config import (
    TaskType,
    convert_string_section_to_config_str,
    convert_to_string,
)
from plex.daily.tasks.logic.conversions import get_timing_uuid_from_task_uuid
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
from plex.daily.timing.base import unpack_timing_uuid
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
    get_page,
    update_task,
)
from plex.transform.base import TRANSFORM, LineSection, Metadata, TransformStr

# critical queues (as it's not a pure replacement)
PREPROCESSED = queue.Queue()

# non critical queues (pure replacement, idempotent)
DELETIONS = queue.Queue()
REGULAR = queue.Queue()


def notion_requestor():
    while True:
        cur_queue = None
        if not PREPROCESSED.empty():
            cur_queue = PREPROCESSED
        elif not DELETIONS.empty():
            cur_queue = DELETIONS
        elif not REGULAR.empty():
            cur_queue = REGULAR
        if cur_queue:
            update_latest_representations(cur_queue.get())
            cur_queue.task_done()


def clear_queues(current_q: queue.Queue) -> None:
    while not current_q.empty():
        try:
            current_q.get(block=False)
        except queue.Empty:
            continue
        current_q.task_done()


def overwrite_tasks_in_notion(datestr: str):
    notion_sections = pull_tasks_from_notion(datestr)
    if notion_sections is not None:
        print("Removing Existing Page...")
        for current_q in [PREPROCESSED, DELETIONS, REGULAR]:
            clear_queues(current_q)
        delete_block(notion_uuid=get_page(datestr)["id"])

    for _ in range(3):  # retry 3 times to account for deletion change propogation
        try:
            return sync_tasks_to_notion(
                datestr, force_push=True, is_create_header=notion_sections is None
            )
        except APIResponseError as error:
            print(error)
        time.sleep(0.5)


def sync_tasks_to_notion(datestr, force_push=False, is_create_header=True) -> bool:
    """Syncs with notion tasks"""
    notion_sections = None if force_push else pull_tasks_from_notion(datestr)

    _, _, new_tasks = split_lines_across_splitter(
        TRANSFORM.construct_content(), is_separate_splitter=True
    )

    is_changed = False
    # find tasks to add, update, delete
    if notion_sections is None:
        # if first time generation, add everything
        print("Pushing Existing Notion Tasks...")
        new_sections = [
            convert_config_str_to_string_section(new_task) for new_task in new_tasks
        ]
        push_tasks_to_notion(
            unflatten_string_sections(new_sections),
            datestr,
        )
        is_changed = True
    else:
        current_tasks = {
            section.notion_uuid: section.parent_notion_uuid
            for section in flatten_string_sections(notion_sections)
        }

        new_regular: list[ChangeSet] = []
        for initial_state in TRANSFORM.get_initial_states():
            if initial_state == "\n":
                continue
            final_state = TRANSFORM.construct_content(focus_lines=[initial_state])
            if len(final_state) == 1 and final_state[0] == initial_state:
                continue
            notion_uuid = TRANSFORM.get_metadata(initial_state).notion_uuid
            if notion_uuid in current_tasks:
                if not final_state:
                    DELETIONS.put(
                        ChangeSet(
                            datestr,
                            notion_uuid,
                            initial_state,
                            final_state,
                            parent_notion_uuid=current_tasks[notion_uuid],
                        )
                    )
                elif (
                    any(
                        TRANSFORM.get_metadata(fs).is_preprocessed for fs in final_state
                    )
                    or len(final_state) > 1
                ):
                    PREPROCESSED.put(
                        ChangeSet(
                            datestr,
                            notion_uuid,
                            initial_state,
                            final_state,
                            is_replace_ok=False,
                            parent_notion_uuid=current_tasks[notion_uuid],
                        )
                    )
                else:
                    new_regular.append(
                        ChangeSet(
                            datestr,
                            notion_uuid,
                            initial_state,
                            final_state,
                            parent_notion_uuid=current_tasks[notion_uuid],
                        )
                    )

        if DELETIONS.empty() and PREPROCESSED.empty() and REGULAR.empty():
            # update regular infrequently - only when the previous batch is fully processed.
            if new_regular:
                # note: we don't clear the queue here to prevent excessive clearing.
                for nreg in new_regular:
                    REGULAR.put(nreg)
                is_changed = True
        else:
            is_changed = True
    return is_changed


@dataclass(frozen=True)
class ChangeSet:
    datestr: str
    notion_uuid: str
    initial_state: str
    final_states: list[str]
    is_replace_ok: bool = True
    parent_notion_uuid: Optional[str] = None


def update_latest_representations(change_set: ChangeSet):
    # get latest str represetation, ignore indentation level.
    final_state_ncontent = convert_sections_to_notion_contents(
        unflatten_string_sections(
            [convert_config_str_to_string_section(fs) for fs in change_set.final_states]
        )
    )
    latest_str_rep = get_latest_str_representation(
        change_set.notion_uuid,
        len(convert_config_str_to_string_section(change_set.initial_state).indentation),
    )
    if latest_str_rep == change_set.initial_state:
        print(
            f"Updating '{repr(change_set.initial_state)}' to '{change_set.final_states}'"
        )
        if len(final_state_ncontent) == 1 and change_set.is_replace_ok:
            update_task(final_state_ncontent[0], notion_uuid=change_set.notion_uuid)
        else:
            if final_state_ncontent:
                add_tasks_after(
                    final_state_ncontent,
                    change_set.notion_uuid,
                    parent_uuid=change_set.parent_notion_uuid,
                    default_page_name=change_set.datestr,
                )
            delete_block(notion_uuid=change_set.notion_uuid)
    else:
        print(
            f"Skipping update: '{repr(change_set.initial_state)}' to '{change_set.final_states}'. Latest String rep is '{repr(latest_str_rep)}'"
        )


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


def pull_tasks_from_notion(datestr: str) -> Optional[list[StringSection]]:
    """pulls tasks from notion and formats them into config lines.

    Args:
        datestr (str): date string.

    Returns:
        list[str]: config lines
    """
    # don't pull tasks if we still have preprocessed items as these could cause duplications
    PREPROCESSED.join()
    return convert_notion_contents_to_string_sections(
        get_contents(default_page_name=datestr)
    )


def push_tasks_to_notion(sections: list[StringSection], datestr: str) -> None:
    """Push notes to notion tasks"""
    add_tasks_after(
        convert_sections_to_notion_contents(sections), default_page_name=datestr
    )


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
    indent_level: int = 0,
    parent_notion_uuid: Optional[str] = None,
) -> Optional[list[StringSection]]:
    sections = []
    fformats = [get_field_formats(i) for i in TaskType]
    if not ncontents:
        return None
    for ncontent in ncontents:
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
                    for (
                        start_diff,
                        start,
                        end,
                        name,
                        uuid,
                        stime,
                        end_diff,
                    ) in re.findall(
                        (
                            rf"({make_regex_parenthesis_non_capturing(start_diff)})?"
                            + rf"({make_regex_parenthesis_non_capturing(fformat.start)})"
                            + rf"({make_regex_parenthesis_non_capturing(fformat.end)})"
                            + rf"({make_regex_parenthesis_non_capturing(fformat.name)})"
                            + rf"({make_regex_parenthesis_non_capturing(fformat.uuid)})"
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
                                uuid=uuid,
                                time=stime,
                                end_diff=end_diff.replace(" ", "\t") or "\t",
                                is_overlap=is_red,
                                children=convert_notion_contents_to_string_sections(
                                    ncontent.children,
                                    indent_level=indent_level + 1,
                                    parent_notion_uuid=ncontent.notion_uuid,
                                ),
                                notion_uuid=ncontent.notion_uuid,
                                parent_notion_uuid=parent_notion_uuid,
                            )
                        )

            # taskgroups
            if ncontent.ntype == NotionType.paragraph:
                if not ncontent.sections or not ncontent.sections[0].content:
                    sections.append(
                        TaskGroupStringSections(
                            is_break=True,
                            notion_uuid=ncontent.notion_uuid,
                            parent_notion_uuid=parent_notion_uuid,
                        )
                    )
                elif ncontent.sections[0].color == "blue":  # best efforts
                    sections.append(
                        TaskGroupStringSections(
                            indentation="\t" * indent_level,
                            user_specified_start_or_end=ncontent.sections[0].content
                            + "\n",
                            notion_uuid=ncontent.notion_uuid,
                            parent_notion_uuid=parent_notion_uuid,
                        )
                    )
                else:
                    content = "".join(section.content for section in ncontent.sections)
                    sections.append(
                        TaskGroupStringSections(
                            indentation="\t" * indent_level,
                            note=content + "\n",
                            notion_uuid=ncontent.notion_uuid,
                            parent_notion_uuid=parent_notion_uuid,
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

    link_uuid = unpack_timing_uuid(
        get_timing_uuid_from_task_uuid(section.uuid.strip().replace("|", ""))[0]
    )[0]
    database_content = DatabaseContent(name=link_uuid, uuid=link_uuid)

    start_diff = section.start_diff.replace("\t", " ")
    if start_diff == " ":
        start_diff = ""
    notion_sections = [
        NotionSection(start_diff, color="green"),  # remove initial start space for UX
        NotionSection(section.start, color="red" if section.is_overlap else "brown"),
        NotionSection(section.end, color="red" if section.is_overlap else "brown"),
        NotionSection(
            section.name,
            color="red" if section.is_overlap else "default",
        ),
        NotionSection(
            section.uuid,
            color="red" if section.is_overlap else "gray",
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
