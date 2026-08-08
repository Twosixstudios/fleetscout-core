# Task ID: DOCS-5.5: Sanitize Agent Rules & Sync Tasks.md Header Status

## Objective
Clean up `Tasks.md` by removing legacy `.clinerules` references, updating agent instructions to reflect the active OpenCode pipeline, and bringing the `Current Status` header up to date with completed Phase 5 milestones.

## Target Files
- `Tasks.md`

## Step-by-Step Requirements
1. **Purge Legacy Rules References:**
   - In `Tasks.md`, update the **Agent Instructions & Guidelines** section.
   - Remove references to `.clinerules/00-global.md`.
   - Update instructions to: *"Always check `CLAUDE.md`, `copilot/pending_task.md`, and `copilot/build_result.md` before starting work."*

2. **Sync Current Status Header:**
   - Update **Active Phase** to: `Phase 5 - Modular Plugins, Hardening & Deploy (Completed)`
   - Update **Target Deliverable** to summarize Phase 5: `RateCon parsing hooks, OSRM/HOS routing plugins, safety interceptor hard lockout, mobile viewport polish, and Streamlit driver UI fixes.`
   - Update **Overall Progress** for Phase 5 to: `4 / 4 Tasks Completed (100%)`

3. **Audit Task Checkboxes:**
   - Verify that all tasks from Phase 1 through Phase 5 (Tasks 1.1–1.4, 2.1–2.3, 3.1–3.4, 4.1–4.4, 5.1–5.4) are marked as completed `[x]`.

## Guardrails & Verification
- Ensure no code files outside `Tasks.md` are modified.
- Verify markdown rendering remains clean and scannable.
- Run `git add . && git commit -m "docs: sanitize agent rules and update Tasks.md status header to Phase 5 complete" && git push origin main` upon successful verification.