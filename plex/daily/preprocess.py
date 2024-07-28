from plex.daily.timing.read import split_lines_across_splitter
from plex.daily.timing.process import get_timing_from_lines, is_valid_timing_str, gather_existing_uuids_from_lines
from plex.daily.tasks.logic.calculations import calculate_times_in_taskgroup_list
from plex.daily.tasks.logic.conversions import get_taskgroups_from_timing_configs
from plex.daily.tasks.config import convert_taskgroups_to_string

def apply_preprocessing(filename: str, datestr: str) -> None:
	with open(filename) as file:
		timing, tasks = split_lines_across_splitter(file.readlines())
		splitter_line, tasks = tasks[0], tasks[1:] # first line of tasks is the splitter
	timing, tasks = process_timings_in_task_section(timing, tasks)

	with open(filename, "w") as file:
		file.writelines(timing + [splitter_line] + tasks)

def process_timings_in_task_section(timing_lines: list[str], task_lines:list[str]) -> tuple[list[str], list[str]]:
	"""
	Args:
		timing_lines (list[str]): timing lies
		task_lines (list[str]): task lines
	"""
	new_task_lines = []
	for task_line in task_lines:
		if is_valid_timing_str(task_line):
			timing_configs, new_timing_lines = get_timing_from_lines([task_line], existing_uuids=gather_existing_uuids_from_lines(timing_lines))
			# add timing
			timing_lines += new_timing_lines

			# add task
			taskgroups = get_taskgroups_from_timing_configs(timing_configs)
			taskgroups = calculate_times_in_taskgroup_list(taskgroups)
			task_line = convert_taskgroups_to_string(taskgroups)
		new_task_lines.append(task_line)
	return timing_lines, new_task_lines
