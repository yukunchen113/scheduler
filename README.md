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
