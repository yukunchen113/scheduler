# TODO:

## Daily Improvements

- allow pulling of timings
  - useful for:
    - other apis (strength app)
    - daily calendar offerings for goals
    - work calendar (oncl, normal day, holiday)
    - default tasks
      - these tasks are every day routine and correspond to a configuration of standard tasks (translation unit)
      - reach out to external libraries for tasks of tasks
      - these tasks will be gathered by "allow default tasks"
  - phase 1:
    - only worry about pulling the task, don't calculate timing unless if it's the default tasks
- allow spec of a hour:min for start/end diffs
- timing improvments:
  - specify time of when a task is supposed to start in timing
  - indicate timing overlaps
- correction of timings
  - must be greater than sum of subtask times?
    - might not be desirable since we can have multiple timing specs, how do you modify that?
- add timing sections
  - current: tasks to do today
  - off: tasks that are not included in today's calculation
  - future: tasks that will be forwarded ot the next day's list
- better estimations for key in deletion/addition

## Calendar Improvements

- add calendar processing

## Other

- documentation
  - enrich features with examples on how to do it
  - add notes on values

# Features:

Given timings, will generate a schedule
You can add sub timings, which will generate subtasks.
If you add or delete timings, the change will be reflected in the tasks.
If you change the main times for the timings, it will be reflected in the tasks

Task schedule can be adjustable you can shift things around to your needs.

You can add or subtract times based on if you started or finished earlier or later than expected

- note, to encourage breaks and increase flexibility, this is how adding/subtracting time works (until end or hard start time) These are called start/end diffs:
  - subtract from task start will shift everything early
  - add to the start will shift everything later
  - subtract from task end will not affect subsequent tasks, only the current task end time. This is to encourage breaks and lessen the need to complete everything early - if you feel the need to complete everything early, plan less.
  - add to the end will shift everything later

You can define a hard start time

- the tasks from then onwards (until a empty line) will be adjusted to this start time.

You can define a soft end time

- the tasks will re-adjust backwards
- this is applied before the subtracts/adds to time

You can add notes to the schedule
