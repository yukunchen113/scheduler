import requests
from notion_client import Client
from pprint import pprint
import functools
from datetime import datetime, date
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

CREDENTIALS_BASEPATH = os.path.join(os.environ["HOME"], ".credentials/")
PAGE_NAME = "Tasks"

def get_secret():
    filepath = os.path.join(CREDENTIALS_BASEPATH, "notion-api-key")
    with open(filepath) as file:
        secret = file.read()
    return secret

@functools.cache
def get_client() -> Client:
    return Client(auth=get_secret())

@functools.cache
def get_page():
    notion = get_client()
    results = notion.search(query=PAGE_NAME).get("results")
    if not results:
        raise ValueError(f"Page '{PAGE_NAME}' not found. Please give your integrations access to a page named '{PAGE_NAME}'")
    return results[0]

def get_contents(block_id:Optional[str] = None):
    notion = get_client()
    if block_id is None:
        block_id = get_page()["id"]
    return notion.blocks.children.list(block_id)

class NotionType(Enum):
    heading_1 = "heading_1"
    heading_2 = "heading_2"
    to_do = "to_do"
    paragraph = "paragraph"
    synced_block = "synced_block"
    bulleted_list_item = "bulleted_list_item"
    
@dataclass
class NotionContent:
    ntype: NotionType
    content: str
    ndatetime: Optional[Union[date, datetime]] = None
    notion_uuid: Optional[str] = None 

@dataclass
class NotionContentGroup:
    contents: list[NotionContent]
    notion_uuid: Optional[str] = None 
    
    @property
    def ntype(self):
        return NotionType.synced_block

def make_notion_json(content: Union[NotionContentGroup, NotionContent]):
    if isinstance(content, NotionContent):
        rich_text = []
        if content.content:
            rich_text.append({'text': {'content': content.content}})
        if content.ndatetime:
            rich_text.append({'mention': {'date': {
                                            'start': content.ndatetime.isoformat()},
                                    'type': 'date'},
                        'type': 'mention'})
        return {content.ntype.value: {'color': 'default', 'rich_text': rich_text}}
    else:
        return {content.ntype.value: {
            "synced_from": None,
            'children': [
                make_notion_json(child) for child in content.contents
            ]
        }}
        
def update_task(n_content: Union[NotionContentGroup, NotionContent]):
    notion = get_client()
    if n_content.notion_uuid is not None: # updated existing block
        if isinstance(n_content, NotionContent):
            return notion.blocks.update(
                n_content.notion_uuid, 
                **make_notion_json(n_content)
            )
        else:
            pass
    return None # no item found

def add_tasks_after(n_contents: list[Union[NotionContentGroup, NotionContent]], after_uuid: Optional[str]= None):
    notion = get_client()
    page_uuid = get_page()["id"]
    # append after specified block
    if after_uuid is None:
        output = notion.blocks.children.append(
            page_uuid,
            children = [make_notion_json(n_content) for n_content in n_contents],
        )["results"]
    else:
        output = notion.blocks.children.append(
            page_uuid,
            children = [make_notion_json(n_content) for n_content in n_contents],
            after = after_uuid
        )["results"]
        
    for n_content, result in zip(n_contents, output):
        n_content.notion_uuid = result["id"]
        if isinstance(n_content, NotionContentGroup):
            for child_content, child_result in zip(n_content.contents, get_contents(block_id=result["id"])["results"]):
                child_content.notion_uuid = child_result["id"]
        
def update_task_set(
    heading: NotionContent,
    next_task: NotionContentGroup,
    current_tasks: list[NotionContentGroup]
):
    """Will update a set of tasks under the form of:
    
    # heading
    next task
    ## task_name
    [ ] todo 1
    [ ] todo 2
    
    will also modify the input in place with proper uuids if not specified
    """
    children = []
    if update_task(heading) is None: # create new
        children += [heading, next_task] + current_tasks
    else:
        if update_task(next_task) is None:
            children.append(next_task)
        children += [
            ctask for ctask in current_tasks
            if update_task(ctask) is None
        ]
    add_tasks_after(children)

def delete_block(block: NotionContent):
    if block.notion_uuid:
        notion = get_client()
        notion.blocks.delete(block.notion_uuid)

if __name__ == "__main__":
    from pprint import pprint
    import time
    # pprint(get_contents())
    i = 0
    while True:
        heading = NotionContent(
            NotionType.heading_1,
            f"Test {i}"
        )
        heading = update_task(heading)
        i += 1
        time.sleep(1)