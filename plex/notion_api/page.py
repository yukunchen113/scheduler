import functools
import os
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pprint import pprint
from typing import Optional, Union

import requests
from notion_client import Client
from notion_client.errors import APIResponseError

CREDENTIALS_BASEPATH = os.path.join(os.environ["HOME"], ".credentials/")
PAGE_NAME = "Schedule"
DATABASE = "Task Details"


def get_secret():
    filepath = os.path.join(CREDENTIALS_BASEPATH, "notion-api-key")
    with open(filepath) as file:
        secret = file.read()
    return secret


@functools.cache
def get_client() -> Client:
    return Client(auth=get_secret())


class PageNotFoundError(ValueError):
    """Page is not found"""


PAGE_CACHE = {}


def get_page(page_name):
    if page_name in PAGE_CACHE:
        return PAGE_CACHE[page_name]
    notion = get_client()
    for result in notion.search(query=page_name).get("results"):
        if not result["archived"] and not result["in_trash"]:
            try:
                if (
                    result["object"] == "database"
                    or "".join(
                        i["plain_text"] for i in result["properties"]["title"]["title"]
                    )
                    == page_name
                ):
                    PAGE_CACHE[page_name] = result
                    return result
            except KeyError:
                pass
    raise PageNotFoundError(
        f"Page '{page_name}' not found. Please give your integrations access to a page named '{page_name}'"
    )


def process_notion_result_to_notion_content(
    result: dict,
    existing_database_content: Optional[dict[str, "DatabaseContent"]] = None,
) -> Optional["NotionContent"]:
    for ntype in NotionType:
        if ntype.value in result and ntype != NotionType.synced_block:
            sections = []
            for nsection in result[ntype.value]["rich_text"]:
                # check for start and end dates:
                if nsection.get("mention") and nsection["mention"].get("date"):
                    date_data = nsection["mention"].get("date")
                    sections.append(
                        NotionSection(
                            content="",
                            start_datetime=datetime.fromisoformat(
                                date_data["start"]
                            ).date()
                            if date_data["start"]
                            else None,
                            end_datetime=datetime.fromisoformat(date_data["end"]).date()
                            if date_data["end"]
                            else None,
                        )
                    )
                else:
                    database_content = None
                    if nsection["text"].get("link"):
                        if existing_database_content is None:
                            database_content = get_database_content_from_row(
                                get_client().pages.retrieve(
                                    uuid.UUID(
                                        nsection["text"]["link"]["url"].replace("/", "")
                                    )
                                )
                            )
                        else:
                            database_content = existing_database_content.get(
                                nsection["text"]["link"]["url"]
                            )

                    sections.append(
                        NotionSection(
                            content=nsection["text"]["content"],
                            color=nsection["annotations"]["color"],
                            database_content=database_content,
                        )
                    )
            return NotionContent(
                ntype=ntype, sections=sections, notion_uuid=result["id"]
            )
    return None


def get_subpages():
    subpages = {}
    for result in (
        get_client().blocks.children.list(get_page(PAGE_NAME)["id"]).get("results")
    ):
        if "child_page" in result:
            PAGE_CACHE[result["child_page"]["title"]] = result
            subpages[result["child_page"]["title"]] = result["id"]
    return subpages


def get_contents(
    block_id: Optional[str] = None, default_page_name: str = PAGE_NAME
) -> list["NotionContent"]:
    contents = []
    notion = get_client()
    if block_id is None:
        try:
            block_id = get_page(default_page_name)["id"]
        except PageNotFoundError:
            return contents
    database_content = {
        make_database_content_into_link(content)["url"]: content
        for content in pull_database_contents_from_notion()
    }
    for result in notion.blocks.children.list(block_id).get("results"):
        notion_content = process_notion_result_to_notion_content(
            result, database_content
        )
        if notion_content is not None:
            if result.get("has_children"):
                notion_content.children = get_contents(
                    block_id=result["id"], default_page_name=default_page_name
                )
            contents.append(notion_content)
    return contents


class NotionType(Enum):
    heading_1 = "heading_1"
    heading_2 = "heading_2"
    to_do = "to_do"
    paragraph = "paragraph"
    synced_block = "synced_block"
    bulleted_list_item = "bulleted_list_item"


@dataclass
class NotionSection:
    content: str
    start_datetime: Optional[Union[date, datetime]] = None
    end_datetime: Optional[Union[date, datetime]] = None
    color: str = "default"
    database_content: Optional["DatabaseContent"] = None


@dataclass
class NotionContent:
    ntype: NotionType
    sections: list[NotionSection]
    notion_uuid: Optional[str] = None
    children: list["NotionContent"] = field(default_factory=list)


@dataclass
class NotionContentGroup:
    contents: list[NotionContent]
    notion_uuid: Optional[str] = None

    @property
    def ntype(self):
        return NotionType.synced_block


def make_database_content_into_link(database_content: "DatabaseContent"):
    link = None
    if database_content and database_content.entry_uuid:
        link = {"url": "/" + database_content.entry_uuid.replace("-", "")}
    return link


def make_notion_json(content: Union[NotionContentGroup, NotionContent]):
    if isinstance(content, NotionContent):
        rich_text = []
        for section in content.sections:
            if section.start_datetime:
                rich_text.append(
                    {
                        "mention": {
                            "date": {
                                "start": None
                                if section.start_datetime is None
                                else section.start_datetime.isoformat(),
                                "end": None
                                if section.end_datetime is None
                                else section.end_datetime.isoformat(),
                            },
                            "type": "date",
                        },
                        "type": "mention",
                    }
                )
            if section.content:
                rich_text.append(
                    {
                        "text": {
                            "content": section.content,
                            "link": make_database_content_into_link(
                                section.database_content
                            ),
                        },
                        "annotations": {"color": section.color},
                    }
                )
        request = {content.ntype.value: {"rich_text": rich_text}}
        if content.ntype not in [
            NotionType.heading_1,
            NotionType.heading_2,
            NotionType.paragraph,
        ]:
            request[content.ntype.value]["children"] = [
                make_notion_json(child) for child in content.children
            ]
        return request
    else:
        return {
            content.ntype.value: {
                "synced_from": None,
                "children": [make_notion_json(child) for child in content.contents],
            }
        }


def update_task(
    n_content: Union[NotionContentGroup, NotionContent],
    notion_uuid: Optional[str] = None,
):
    notion = get_client()
    if notion_uuid is None:
        notion_uuid = n_content.notion_uuid

    update_database_contents_in_notion(
        get_all_database_contents_from_notion_content(n_content)
    )

    if notion_uuid is not None:  # updated existing block
        if isinstance(n_content, NotionContent):
            try:
                return notion.blocks.update(notion_uuid, **make_notion_json(n_content))
            except APIResponseError as err:
                print(f"Skipping update for {n_content}. Error: {str(err)}")
                pass
    return None  # no item found


def get_all_database_contents_from_notion_content(
    content: Union[NotionContentGroup, NotionContent]
):
    database_contents = []
    if isinstance(content, NotionContentGroup):
        for subcontent in content.contents:
            database_contents += get_all_database_contents_from_notion_content(
                subcontent
            )
    elif isinstance(content, NotionContent):
        for section in content.sections:
            if section.database_content is not None:
                database_contents.append(section.database_content)
            for subcontent in content.children:
                database_contents += get_all_database_contents_from_notion_content(
                    subcontent
                )
    return database_contents


def create_page(page_name: str):
    notion = get_client()
    parent_id = get_page(PAGE_NAME)["id"]
    page = notion.pages.create(
        parent={"page_id": parent_id},
        properties={
            "title": [{"text": {"content": page_name}}],
        },
    )
    PAGE_CACHE[page_name] = page
    return page


def clear_page_cache():
    for key in list(PAGE_CACHE.keys()):
        PAGE_CACHE.pop(key)


def add_tasks_after(
    n_contents: list[Union[NotionContentGroup, NotionContent]],
    after_uuid: Optional[str] = None,
    parent_uuid: Optional[str] = None,
    default_page_name: str = PAGE_NAME,
):
    notion = get_client()
    if parent_uuid is None:
        try:
            parent_uuid = get_page(default_page_name)["id"]
        except PageNotFoundError:
            parent_uuid = create_page(default_page_name)["id"]
            print(f"Creating new notion page {default_page_name}")

    database_contents = []
    for content in n_contents:
        database_contents += get_all_database_contents_from_notion_content(content)

    update_database_contents_in_notion(database_contents)

    # append after specified block
    if after_uuid is None:
        output = notion.blocks.children.append(
            parent_uuid,
            children=[make_notion_json(n_content) for n_content in n_contents],
        )["results"]
    else:
        output = notion.blocks.children.append(
            parent_uuid,
            children=[make_notion_json(n_content) for n_content in n_contents],
            after=after_uuid,
        )["results"]

    for n_content, result in zip(n_contents, output):
        n_content.notion_uuid = result["id"]
        if isinstance(n_content, NotionContentGroup):
            for child_content, child_result in zip(
                n_content.contents,
                get_contents(
                    block_id=result["id"], default_page_name=default_page_name
                )["results"],
            ):
                child_content.notion_uuid = child_result["id"]


def delete_block(
    block: Optional[NotionContent] = None, notion_uuid: Optional[str] = None
):
    if notion_uuid is None:
        notion_uuid = block.notion_uuid
    if notion_uuid:
        notion = get_client()
        notion.blocks.delete(notion_uuid)
        for page_name, page in list(PAGE_CACHE.items()):
            if page["id"] == notion_uuid:
                PAGE_CACHE.pop(page_name)


@dataclass
class DatabaseContent:
    name: str
    uuid: str
    notes: list[NotionContent] = field(default_factory=list)
    entry_uuid: str = ""


class DatabaseProperties(Enum):
    """Do not chase these values unless you want drop the database"""

    name = "name"
    uuid = "uuid"


@functools.cache
def get_database():
    notion = get_client()
    try:
        database = get_page(DATABASE)
        if database["in_trash"]:
            raise ValueError("Database is deleted.")
    except PageNotFoundError:
        database = notion.databases.create(
            parent={"type": "page_id", "page_id": get_page(PAGE_NAME)["id"]},
            title=[
                {
                    "type": "text",
                    "text": {
                        "content": DATABASE,
                    },
                },
            ],
            properties={
                DatabaseProperties.name.value: {
                    "title": {},
                },
                DatabaseProperties.uuid.value: {
                    "rich_text": {},
                },
            },
        )
    return database


def get_database_content_from_row(result):
    return DatabaseContent(
        name=result["properties"]["name"]["title"][0]["text"]["content"],
        uuid=result["properties"]["uuid"]["rich_text"][0]["text"]["content"],
        entry_uuid=result["id"],
    )


def pull_database_contents_from_notion():
    try:
        return [
            get_database_content_from_row(result)
            for result in get_client()
            .databases.query(get_page(DATABASE)["id"])
            .get("results")
        ]
    except (ValueError, PageNotFoundError):
        return []


def update_database_contents_in_notion(contents: list[DatabaseContent]):
    notion = get_client()
    database = get_database()
    cur_contents = {
        content.uuid: content for content in pull_database_contents_from_notion()
    }

    for content in contents:
        if not content.entry_uuid:
            if content.uuid in cur_contents:
                content.entry_uuid = cur_contents[content.uuid].entry_uuid
            else:
                page = notion.pages.create(
                    parent={"type": "database_id", "database_id": database["id"]},
                    properties={
                        DatabaseProperties.name.value: {
                            "title": [{"text": {"content": content.name}}],
                        },
                        DatabaseProperties.uuid.value: {
                            "rich_text": [{"text": {"content": content.uuid}}],
                        },
                    },
                )
                content.entry_uuid = page["id"]
                cur_contents[content.uuid] = content


def get_block(block_id: int):
    notion = get_client()
    blocks = notion.blocks.retrieve(block_id)
    if blocks.get("archived") or blocks.get("in_trash"):
        return None
    return process_notion_result_to_notion_content(blocks)


if __name__ == "__main__":
    from pprint import pprint

    pprint(get_block("0989afe4-c388-4595-8663-ecc29229a6bc"))
