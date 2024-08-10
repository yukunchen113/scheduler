from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pprint import pformat, pprint
from typing import Any, Optional, TypedDict, Union


class LineSection(Enum):
    timing = "timing"
    task = "task"
    neither = "neither"


@dataclass(frozen=True)
class LineInfo:
    is_spacing_element: bool = False
    is_taskgroup_note: bool = False


@dataclass(frozen=True)
class Metadata:
    section: Optional[LineSection] = None
    notion_uuid: Optional[str] = None
    line_info: Optional[LineInfo] = None
    is_preprocessed: bool = False


@dataclass(frozen=True)
class State:
    sequence_id: int
    content: str
    metadata: Metadata

    add_after_sequence_id: int


class UpdateType(Enum):
    append = "append"  # appends after the previous sequence element
    update = "update"  # directly modifies previous sequence element


@dataclass(frozen=True)
class Update:
    sequence_id: int
    prev_sequence_id: int
    content: Optional[str]
    metadata: Metadata

    add_after_sequence_id: int
    update_type: UpdateType


class TransformStr(str):
    def __new__(cls, *ar, transform_id: int = -1, **kw):
        obj = str.__new__(cls, *ar, **kw)
        obj.transform_id = transform_id
        return obj


class TransformInt(int):
    def __new__(cls, *ar, transform_id: int = -1, **kw):
        obj = int.__new__(cls, *ar, **kw)
        obj.transform_id = transform_id
        return obj


class TransformDatetime(datetime):
    def add_transform_id(self, transform_id):
        self.transform_id = transform_id


TransformType = Union[TransformStr, TransformInt, TransformDatetime]


def make_transform_type(content: Any, transform_id: int) -> TransformType:
    if content is None:
        return None
    elif isinstance(content, str):
        return TransformStr(content, transform_id=transform_id)
    elif isinstance(content, int):
        return TransformInt(content, transform_id=transform_id)
    elif isinstance(content, datetime):
        return TransformDatetime(content, transform_id=transform_id)
    else:
        raise ValueError(f"Type '{type(content)}' is not a supported transform type")


class Transform:
    def __init__(self):
        self.sequence_id = -1
        self.data: dict[int, Union[State, Update]] = {}
        self.current_view = set()
        self.sequence_updates = {}

    def clear(self):
        self.__init__()

    # Getters
    def get_most_recent_sequence_id(self, sequence_id: int) -> int:
        while sequence_id in self.sequence_updates:
            sequence_id = self.sequence_updates[sequence_id]
        return sequence_id

    def is_updated(self, line: TransformType) -> bool:
        return line.transform_id in self.sequence_updates

    def get_metadata(self, line: TransformType) -> Metadata:
        try:
            return self.data.get(line.transform_id).metadata
        except AttributeError:
            return None

    def get_initial_states(self):
        return [
            TransformStr(state.content, transform_id=seq_id)
            for seq_id, state in self.data.items()
            if isinstance(state, State)
        ]

    # adding/updating/deleting content
    def append(
        self,
        content: str,
        metadata: Optional[Metadata] = None,
        add_after_content: Optional[str] = None,
    ) -> TransformType:
        self.sequence_id += 1
        if metadata is None:
            metadata = Metadata()
        add_after_sequence_id = self.sequence_id - 1
        if add_after_content is not None:
            add_after_sequence_id = add_after_content.transform_id
        self.data[self.sequence_id] = State(
            sequence_id=self.sequence_id,
            content=content,
            metadata=metadata,
            add_after_sequence_id=add_after_sequence_id,
        )
        self.current_view.add(self.sequence_id)
        return make_transform_type(content, transform_id=self.sequence_id)

    def replace(
        self,
        prev_content: TransformType,
        content: Optional[Any],
        metadata: Optional[Metadata] = None,
        *,
        soft_failure: bool = False,
    ) -> Optional[TransformType]:
        if not hasattr(prev_content, "transform_id"):
            if not soft_failure:
                raise ValueError(
                    "Provided previous content does not have "
                    f"a transform_id and is '{repr(prev_content)}'. "
                    f"Replacement content is '{repr(content)}'"
                )
            else:
                return content

        state = self.data.get(prev_content.transform_id)
        sequence_id = self.get_most_recent_sequence_id(state.sequence_id)
        state = self.data[sequence_id]
        if state:
            self.sequence_id += 1
            assert state.content is not None
            if metadata is None:
                metadata = state.metadata
            self.data[self.sequence_id] = Update(
                sequence_id=self.sequence_id,
                prev_sequence_id=state.sequence_id,
                content=content,
                metadata=metadata,
                add_after_sequence_id=state.add_after_sequence_id,
                update_type=UpdateType.update,
            )
            self.sequence_updates[state.sequence_id] = self.sequence_id
            self.current_view.remove(state.sequence_id)
            if content is not None:
                self.current_view.add(self.sequence_id)
                return make_transform_type(content, transform_id=self.sequence_id)

    def delete(self, content: TransformType) -> None:
        return self.replace(content, None)

    def add_after(
        self,
        prev_content: TransformType,
        new_contents: list[str],
        add_after: TransformType,
        metadata: Optional[Metadata] = None,
        *,
        soft_failure: bool = False,
    ) -> list[TransformType]:
        if not hasattr(prev_content, "transform_id"):
            if not soft_failure:
                raise ValueError(
                    "Provided previous content does not have "
                    f"a transform_id and is '{repr(prev_content)}'. "
                    f"new content is '{repr(new_contents)}'"
                )
            else:
                return new_contents
        if not hasattr(add_after, "transform_id"):
            if not soft_failure:
                raise ValueError(
                    "Provided add after does not have "
                    f"a transform_id and is '{repr(add_after)}'. "
                    f"add after content is '{repr(new_contents)}'"
                )
            else:
                return new_contents

        if metadata is None:
            metadata = Metadata()

        transformed_content = []
        add_after_id = self.get_most_recent_sequence_id(add_after.transform_id)
        prev_sequence_id = self.get_most_recent_sequence_id(prev_content.transform_id)

        assert self.data[add_after_id].content is not None
        assert self.data[prev_sequence_id].content is not None

        # add new strings
        for content in new_contents:
            self.sequence_id += 1
            variable = Update(
                sequence_id=self.sequence_id,
                prev_sequence_id=prev_sequence_id,
                content=content,
                metadata=metadata,
                add_after_sequence_id=add_after_id,
                update_type=UpdateType.append,
            )
            add_after_id = self.sequence_id
            self.current_view.add(self.sequence_id)
            self.data[self.sequence_id] = variable
            transformed_content.append(make_transform_type(content, self.sequence_id))
        return transformed_content

    def nreplace(
        self,
        prev_content: TransformType,
        new_contents: list[str],
        metadata: Optional[Metadata] = None,
    ) -> list[TransformType]:
        if metadata is None:
            metadata = self.data[prev_content.transform_id].metadata
        transformed_content = self.add_after(
            prev_content, new_contents, prev_content, metadata
        )
        self.delete(prev_content)
        return transformed_content

    # replaying changes:
    def construct_content(
        self, focus_lines: Optional[TransformType] = None
    ) -> list[TransformType]:
        tail = {}
        head = {"content": None, "next": tail}
        node_index = {-1: head}

        focus_graph_id_nodes = (
            [focus_line.transform_id for focus_line in focus_lines]
            if focus_lines
            else []
        )

        for seq_id in range(len(self.data)):
            state = self.data[seq_id]

            # validations
            if isinstance(state, Update):
                from pprint import pprint

                if state.prev_sequence_id not in node_index:
                    output = [
                        v
                        for _, v in self.data.items()
                        if isinstance(v, Update)
                        and v.prev_sequence_id == state.prev_sequence_id
                    ]
                    pprint(self.data[state.prev_sequence_id])
                    pprint(output)
                    exit()

            # if focus graph is specified,
            if (
                isinstance(state, Update)
                and state.prev_sequence_id in focus_graph_id_nodes
            ):
                if (
                    state.add_after_sequence_id in focus_graph_id_nodes
                    or state.update_type == UpdateType.update
                ):
                    focus_graph_id_nodes.append(state.sequence_id)

            # construct output
            content = make_transform_type(state.content, state.sequence_id)
            if isinstance(state, State):
                new_node = {
                    "content": content,
                    "next": node_index[state.add_after_sequence_id]["next"],
                }
                node_index[state.add_after_sequence_id]["next"] = new_node
                node_index[state.sequence_id] = new_node
            if isinstance(state, Update):
                if state.update_type == UpdateType.append:
                    new_node = {
                        "content": content,
                        "next": node_index[state.add_after_sequence_id]["next"],
                    }
                    node_index[state.add_after_sequence_id]["next"] = new_node
                    node_index[state.sequence_id] = new_node
                elif state.update_type == UpdateType.update:
                    new_node = node_index.pop(state.prev_sequence_id)
                    new_node["content"] = content
                    node_index[state.sequence_id] = new_node

        contents = []
        focus_output = []
        while head != tail:
            if head["content"] is not None:
                contents.append(head["content"])
                if head["content"].transform_id in focus_graph_id_nodes:
                    focus_output.append(head["content"])
            head = head["next"]
        if focus_lines is not None:
            return focus_output
        return contents


TRANSFORM = Transform()
