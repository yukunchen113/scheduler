# Plex VS Code Extension

Native CodeLens, live in-editor controls, and silent background evaluation for the Plex time-blocking scheduler.

## Features

* **Interactive CodeLens**:
  * **Week Header**: `Recalculate Week`, `Export to Daily Files`, `Re-Init with Routine...`
  * **Day Headers**: Live status badges (`📊 6h05m scheduled | 4h10m slack | OK`), `Export Day`, `Insert Routine...`
  * **Daily Files**: `Run Plex Engine`, `Push to Google Calendar`
* **Silent Auto-Evaluation on Save**:
  * Hit `Cmd+S` in any `weekly/*.txt` file — hours, slack, and bedtime warnings recalculate instantly in-place without running any background terminal command.
* **Status Bar Integration**:
  * Persistent summary at the bottom right (`📅 W41: 27.5h scheduled | 18.3h slack (ALL OK)`).
* **Keyboard Shortcuts**:
  * `Cmd+K E`: Export week to daily files.
  * `Cmd+K R`: Recalculate weekly plan.
