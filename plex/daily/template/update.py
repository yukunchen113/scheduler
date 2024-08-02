from plex.daily.template.routines import update_routine_templates
from plex.daily.template.peers import update_peer_commands


def update_templates_in_file(lines: list[str], datestr: str, is_main_file:bool) -> list[str]:
    lines = update_peer_commands(lines)
    return update_routine_templates(lines, datestr, is_main_file)