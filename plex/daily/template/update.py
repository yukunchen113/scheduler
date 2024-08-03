from plex.daily.template.peers import update_peer_commands
from plex.daily.template.routines import update_routine_templates


def update_templates(lines: list[str], datestr: str, is_main_file: bool) -> list[str]:
    lines = update_peer_commands(lines)
    return update_routine_templates(lines, datestr, is_main_file)
