# Phase 3: Desktop Dispatch Portal & Load Management

## Execution Focus
* **Active Milestone:** Phase 3 - Desktop Dispatch Portal
* **Current Objective:** Build out Task 3.2 (Load Creation & Dispatch Panel) and Task 3.3 (Active Load Watch Board).

## Architecture Standards
* **Modularity:** Keep UI components isolated inside `src/ui/` (e.g., `yard_board.py`, `dispatch_panel.py`) and wire them into `app.py`.
* **Database Access:** Route DB mutations through async service functions in `src/core/services.py`.