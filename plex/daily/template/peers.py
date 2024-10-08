"""
Adds the following templates to be able to exchange data between config peers

First, perform push data
Next, ensure that the file being communicated with is fully evaluated (No templates)
Finally, read data to be pulled.


Here are the currently accepted commands:

[<filename>] - or - [<filename>:summary]
- this generates the overall timing in the file specified (no extension)
- creates: [<filename>] (T), where T is the timedelta of the day.
- this is update-able, so (T) will be updated

[<filename>:send]
- this will send the specified data below this marking to the file specified.
- adds new data to beginning of the specified file.
- will remove the sent data after sending.
- selects all data until another [<filename>:command], [:end], or SPLITTER is detected.
"""

import os
import re
from datetime import datetime
from typing import TypedDict

from plex.daily.config_format import (
    SPLITTER,
    TIME_FORMAT,
    TIMEDELTA_FORMAT,
    make_daily_filename,
)
from plex.daily.template.base import ReplacementsType
from plex.daily.template.calculations import evaluate_config_duration
from plex.daily.template.config import process_replacements
from plex.transform.base import TRANSFORM, LineSection, Metadata, TransformStr

COMMAND_PATTERN = r"\[([^:]+)?(?:\:([^:]+))?\](?: \({0}:(?:\|{1}-{1})?\))?".format(
    TIMEDELTA_FORMAT, TIME_FORMAT
)


class CommandSpec(TypedDict):
    target: str
    command: str
    commandline: str
    lines: list[str]


def get_peer_commands(
    lines: list[TransformStr],
) -> tuple[list[TransformStr], list[CommandSpec]]:
    is_command = False
    commands: list[CommandSpec] = []
    new_lines = []
    for idx, line in enumerate(lines):
        if line.startswith(SPLITTER):
            # end previous command.
            new_lines += lines[idx:]
            break
        if re.match(COMMAND_PATTERN, line):
            # start new command
            is_command = True
            matches = re.findall(COMMAND_PATTERN, line)
            assert len(matches) == 1
            target, command = matches[0]
            new_lines.append(line)

            # process end command
            if command == "end":
                assert not target, "Target must not be specified for end command."
                is_command = False
                continue

            assert (
                target
            ), f"filename must be specified except for end command but is '{line}'"
            # process commands that don't accumulate
            if command == "":
                command = "default"
                is_command = False

            if command == "summary":
                is_command = False

            commands.append(
                {"command": command, "commandline": line, "target": target, "lines": []}
            )
        else:
            if is_command:
                # accumulate lines for action:
                commands[-1]["lines"].append(line)
                TRANSFORM.delete(line)
            else:
                # accumulate lines that don't correspond to command
                new_lines.append(line)
    return new_lines, commands


def update_commandline_with_duration(
    command: CommandSpec, return_time_range: bool = False
) -> str:
    # check if is datestr, if it is, then use that as datestr otherwise, use today.
    try:
        # validate datestr
        datestr = datetime.strptime(command["target"], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        datestr = datetime.today().strftime("%Y-%m-%d")
    total_time_str = evaluate_config_duration(
        command["target"], datestr, return_time_range
    )
    target, commandstr = re.findall(COMMAND_PATTERN, command["commandline"])[0]
    if commandstr:
        commandstr = ":" + commandstr
    return f"[{target}{commandstr}] ({total_time_str})\n"


def process_command_and_get_replacement(command: CommandSpec) -> ReplacementsType:
    replacements: ReplacementsType = {}
    if command["command"] == "send":
        if command["lines"]:
            filename = make_daily_filename(command["target"], is_create_file=True)
            print(f"Sending data to {command['target']}")
            with open(filename, "r") as f:
                lines = command["lines"] + ["\n"] + f.readlines()
            with open(filename, "w") as f:
                f.writelines(lines)
    # update commandline command with duration
    replacements[command["commandline"]] = [
        update_commandline_with_duration(
            command, return_time_range=command["command"] == "summary"
        )
    ]
    return replacements


def update_peer_commands(lines: list[TransformStr]) -> list[TransformStr]:
    new_lines, commands = get_peer_commands(lines)
    replacements: ReplacementsType = {}
    order = ["send", "summary", "default"]
    commands = sorted(commands, key=lambda command: order.index(command["command"]))
    for command in commands:
        replacements.update(process_command_and_get_replacement(command))
    return process_replacements(new_lines, replacements)
